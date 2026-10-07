"""Module F: inconsistency detection across the facts of all PVs of a case.

Every rule compares two sentences (from the same PV or from different PVs) and returns
an incoherence with evidence, so a human can check it. Rules are conservative on purpose:
a false positive costs the investigator time, a missed one is caught by the human review.
"""
from datetime import date

from app.modules.pv.nlp import DISTANCES, fold, person_key

SPEED_KMH = {"avion": 800, "train": 320, "voiture": 130, "sol": 320}


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _fr(iso: str) -> str:
    d = _d(iso)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def _people(f: dict) -> set[str]:
    keys = {person_key(p) for p in f["persons"]}
    if f["first_person"] and f["witness"]:
        keys.add(person_key(f["witness"]))
    return {k for k in keys if k}


def _span(f: dict) -> tuple[date, date] | None:
    if f["range"]:
        return _d(f["range"][0]), _d(f["range"][1])
    if f["dates"]:
        return _d(min(f["dates"])), _d(max(f["dates"]))
    return None


def _range_txt(span: tuple[date, date]) -> str:
    if span[1].year > 2900:
        return f"depuis le {span[0].strftime('%d/%m/%Y')}"
    return f"du {span[0].strftime('%d/%m/%Y')} au {span[1].strftime('%d/%m/%Y')}"


def _evidence(*facts: dict) -> list[dict]:
    return [{"pv_id": f["pv"], "excerpt": f["text"]} for f in facts]


def _item(kind: str, severity: str, description: str, *facts: dict) -> dict:
    return {"type": kind, "severity": severity, "description": description,
            "pv_references": list(dict.fromkeys(f["pv"] for f in facts)), "evidence": _evidence(*facts)}


def _temporal(facts: list[dict]) -> list[dict]:
    out = []
    compromised = [f for f in facts if "compromise" in f["kinds"] and f["dates"]]
    actions = [f for f in facts if "action" in f["kinds"] and f["dates"]]
    for c in compromised:
        dc = min(c["dates"])
        for a in actions:
            da = min(a["dates"])
            if da > dc:
                delta = (_d(da) - _d(dc)).days
                out.append(_item(
                    "temporelle", "haute",
                    f"Chronologie impossible : operation autorisee le {_fr(da)} (PV {a['pv']}) alors que le "
                    f"compte est declare compromis le {_fr(dc)} (PV {c['pv']}), soit {delta} jour(s) apres.", a, c))
    for ab in (f for f in facts if "absence" in f["kinds"]):
        span, who = _span(ab), _people(ab)
        if not span or not who:
            continue
        for seen in (f for f in facts if "seen" in f["kinds"] and f["dates"] and f is not ab):
            hit = [d for d in seen["dates"] if span[0] <= _d(d) <= span[1]]
            if hit and (who & {person_key(p) for p in seen["persons"]}):
                out.append(_item(
                    "temporelle", "haute",
                    f"Une personne est vue le {_fr(hit[0])} (PV {seen['pv']}) alors qu'elle declare etre absente "
                    f"{_range_txt(span)} (PV {ab['pv']}).", seen, ab))
    return out


def _geographic(facts: list[dict]) -> list[dict]:
    out = []
    for f in facts:
        t = f["travel"]
        if not t:
            continue
        a, b = t["from"], t["to"]
        dist = DISTANCES.get((a, b)) or DISTANCES.get((b, a))
        if not dist:
            continue
        needed = dist / SPEED_KMH[t["mode"]]
        if t["hours"] < needed * 0.95:
            mode = {"sol": "par voie terrestre", "avion": "en avion", "train": "en train", "voiture": "en voiture"}[t["mode"]]
            out.append(_item(
                "geographique", "haute",
                f"Trajet {a.capitalize()} - {b.capitalize()} ({dist} km) declare en {t['hours']:g} h : "
                f"au moins {needed:.1f} h sont necessaires {mode} (PV {f['pv']}).", f))
    for ab in (f for f in facts if "absence" in f["kinds"] and f["places"]):
        who = _people(ab)
        span = _span(ab)
        if not who:
            continue
        for on in (f for f in facts if "onsite" in f["kinds"] and f is not ab):
            if not (who & _people(on)) and not (who & {person_key(p) for p in on["persons"]}):
                continue
            on_span = _span(on)
            if span and on_span:
                if not (on_span[0] <= span[1] and span[0] <= on_span[1]):
                    continue
                severity, note = "haute", ""
            else:
                severity, note = "moyenne", " (dates absentes : a verifier)"
            out.append(_item(
                "geographique", severity,
                f"Presence sur site (PV {on['pv']}) incompatible avec une absence declaree a "
                f"{ab['places'][0]} (PV {ab['pv']}){note}.", on, ab))
    return out


def _factual(facts: list[dict]) -> list[dict]:
    out = []
    seen_pairs = set()
    states = [(f, s) for f in facts for s in f["states"]]
    for i, (f1, s1) in enumerate(states):
        for f2, s2 in states[i + 1:]:
            if f1 is f2 or fold(s1[0]) != fold(s2[0]) or s1[1] != s2[1] or s1[2] == s2[2]:
                continue
            if f1["dates"] and f2["dates"] and set(f1["dates"]).isdisjoint(f2["dates"]):
                continue
            key = (id(f1), id(f2))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            out.append(_item(
                "factuelle", "haute",
                f"Declarations contradictoires sur '{s1[0]}' ({s1[1]}) : "
                f"{'oui' if s1[2] else 'non'} (PV {f1['pv']}) contre {'oui' if s2[2] else 'non'} (PV {f2['pv']}).",
                f1, f2))
    day = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    for c in (f for f in facts if "click" in f["kinds"]):
        for r in (f for f in facts if "receive" in f["kinds"]):
            if c["dates"] and r["dates"]:
                bad = min(c["dates"]) < min(r["dates"])
                when_c, when_r = _fr(min(c["dates"])), _fr(min(r["dates"]))
            elif c["weekdays"] and r["weekdays"] and not c["dates"] and not r["dates"]:
                bad = c["weekdays"][0] < r["weekdays"][0]
                when_c, when_r = day[c["weekdays"][0]], day[r["weekdays"][0]]
            else:
                continue
            if bad:
                out.append(_item(
                    "factuelle", "haute",
                    f"Piece jointe ouverte ({when_c}, PV {c['pv']}) avant sa reception ({when_r}, PV {r['pv']}).", c, r))
    return out


def detect(facts: list[dict]) -> list[dict]:
    """All inconsistencies for the facts of one case, without duplicates."""
    found, seen = [], set()
    for inc in _temporal(facts) + _geographic(facts) + _factual(facts):
        key = (inc["type"], inc["description"])
        if key not in seen:
            seen.add(key)
            found.append(inc)
    return found
