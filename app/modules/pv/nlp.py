"""Module F: entity and event extraction from interview reports (PV).

spaCy (fr_core_news_lg) supplies persons and places. The French model has no DATE or
MONEY label, so dates, times, amounts, IP addresses and event facts come from rules.
Everything is matched on an accent-folded copy of the text with identical length, so
offsets always line up with the original.
"""
import re
import unicodedata
from collections import Counter
from datetime import date
from functools import lru_cache

MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
WEEKDAYS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
MONTH_RE = "|".join(MONTHS)
WEEKDAY_RE = "|".join(WEEKDAYS)

# Major French cities (canonical display name by folded key) used for places and travel checks.
CITIES = {"paris": "Paris", "lyon": "Lyon", "marseille": "Marseille", "bordeaux": "Bordeaux",
          "lille": "Lille", "toulouse": "Toulouse", "nantes": "Nantes", "strasbourg": "Strasbourg",
          "nice": "Nice", "rennes": "Rennes", "montpellier": "Montpellier", "nancy": "Nancy"}
GENERIC_PLACES = {"siege social": "siege social", "domicile": "domicile", "agence": "agence"}
# Approximate road distances in km (symmetric).
DISTANCES = {("paris", "lyon"): 465, ("paris", "marseille"): 775, ("paris", "bordeaux"): 580,
             ("paris", "lille"): 225, ("paris", "toulouse"): 680, ("paris", "nantes"): 385,
             ("paris", "strasbourg"): 490, ("paris", "nice"): 930, ("paris", "rennes"): 350,
             ("paris", "montpellier"): 750, ("paris", "nancy"): 390, ("lyon", "marseille"): 315,
             ("lyon", "nice"): 470, ("lyon", "bordeaux"): 550, ("lyon", "toulouse"): 540,
             ("marseille", "nice"): 200, ("marseille", "toulouse"): 405, ("bordeaux", "toulouse"): 245,
             ("lille", "lyon"): 700, ("lyon", "strasbourg"): 490}

TITLES = re.compile(r"^(m\.?|mr|mme|mlle|monsieur|madame|mademoiselle|dr|docteur|me|maitre)\s+", re.I)
PLACE_RE = re.compile(r"\b(" + "|".join(list(CITIES) + list(GENERIC_PLACES)) + r")\b")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
AMOUNT_RE = re.compile(r"(\d{1,3}(?:[   .]\d{3})+|\d+)(?:,(\d{1,2}))?\s*(euros?|eur\b|€)")
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])\s?(?:h|heures?)\s?([0-5]\d)?\b|\b([01]?\d|2[0-3]):([0-5]\d)\b")
DATE_NUM = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b"
                      r"|\b(\d{1,2})[-.](\d{1,2})[-.](\d{4}|\d{2})\b")
DATE_TXT = re.compile(r"\b(1er|\d{1,2})\s+(" + MONTH_RE + r")(?:\s+(\d{4}))?\b")
RANGE_TXT = re.compile(r"\bdu\s+(1er|\d{1,2})(?:\s+(" + MONTH_RE + r"))?(?:\s+(\d{4}))?\s+au\s+(1er|\d{1,2})\s+("
                       + MONTH_RE + r")(?:\s+(\d{4}))?\b")
TITLED_PERSON = re.compile(
    r"\b(?:M\.|Mme|Mlle|Mr|Dr|Monsieur|Madame|Mademoiselle|Docteur|Maître)\s+"
    r"([A-ZÀ-Ý][\w'’-]+(?:\s+[A-ZÀ-Ý][\w'’-]+)*)")
WEEKDAY_RX = re.compile(r"\b(" + WEEKDAY_RE + r")\b")

KIND_PATTERNS = {
    "compromise": re.compile(r"compromis|pirat|hack|frauduleu|usurp|intrusion|\bvole\b|\bvol\b"),
    "action": re.compile(r"\b(autoris|valid|ordonn)\w*"),
    "absence": re.compile(r"vacances|\bconges?\b|\babsent|en deplacement|\bvoyage"),
    "seen": re.compile(r"\b(vu|vue|vus|croise|croisee|rencontre|rencontree|apercu|aperçu)\b"),
    "click": re.compile(r"\bclique|\bouvert (la|le|un|une|cette|ce)\s+(piece|lien|mail|message|fichier)"),
    "receive": re.compile(r"(mail|courriel|message|piece jointe).{0,40}\b(recu|recue|arrive|arrivee)\b"
                          r"|\b(recu|recue|arrive|arrivee)\b.{0,40}(mail|courriel|message|piece jointe)"),
    "onsite": re.compile(r"sur place|au bureau|au siege|(connexion|session|ssh|login).{0,60}\b(192\.168|10\.\d|172\.(1[6-9]|2\d|3[01]))"
                         r"|\b(192\.168|10\.\d|172\.(1[6-9]|2\d|3[01]))[\d.]*.{0,60}(connexion|session|ssh|login)"),
}
FIRST_PERSON = re.compile(r"\b(je|moi|mon|ma|mes)\b|\bj'")
STATE_RE = re.compile(r"\b(?:la|le|l'|les|une?|cette|ce)\s*(\w+)\s+(?:n'|ne\s+)?(?:etait|etaient|est|sont|avait ete|a ete|restait)"
                      r"\s+(pas\s+)?(?:bien\s+|toujours\s+|deja\s+)?(\w+)")
STATES = {"ouvert": ("ouverture", True), "ferm": ("ouverture", False), "allum": ("alimentation", True),
          "eteint": ("alimentation", False), "verrouill": ("verrou", True), "deverrouill": ("verrou", False),
          "activ": ("activation", True), "actif": ("activation", True), "desactiv": ("activation", False),
          "inactif": ("activation", False), "present": ("presence", True), "absent": ("presence", False),
          "connect": ("connexion", True), "deconnect": ("connexion", False)}
TRAVEL_RE = re.compile(r"\bde\s+(" + "|".join(CITIES) + r")\s+(?:a|jusqu'?a|vers)\s+(" + "|".join(CITIES) + r")\b"
                       r".{0,60}?\ben\s+(\d+(?:[.,]\d+)?|une|un|deux|trois)\s*(h|heures?|min|minutes?)(?:\s*(\d{2}))?\b")
NUM_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3}
SKIP_FACTS = re.compile(r"^\s*(date|cas|temoin|suspect|investigateur|signature|proces-verbal)\b")


def fold(text: str) -> str:
    """Lowercase and strip accents character by character, so the length never changes."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0]
        low = base.lower()
        out.append(low if len(low) == 1 else base)
    return "".join(out)


@lru_cache(maxsize=1)
def get_nlp():
    import spacy
    return spacy.load("fr_core_news_lg", exclude=["parser", "lemmatizer", "morphologizer", "attribute_ruler"])


def clean_person(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" ,.;:()")
    return TITLES.sub("", name).strip()


def person_key(name: str) -> str:
    parts = fold(clean_person(name)).split()
    return parts[-1] if parts else ""


def _to_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(f: str, year: int) -> tuple[list[tuple[int, int, date]], tuple[date, date] | None]:
    """Dates found in one folded sentence, plus a (start, end) range if the sentence has one."""
    masked = IP_RE.sub(lambda m: " " * len(m.group()), f)
    found: list[tuple[int, int, date]] = []
    rng = None
    taken: list[tuple[int, int]] = []
    m = RANGE_TXT.search(masked)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        yy = int(y2 or y1 or year)
        mm2 = MONTHS[m2]
        mm1 = MONTHS[m1] if m1 else mm2
        a = _to_date(int(y1 or yy), mm1, 1 if d1 == "1er" else int(d1))
        b = _to_date(yy, mm2, 1 if d2 == "1er" else int(d2))
        if a and b:
            rng = (a, b)
            found += [(m.start(), m.end(), a), (m.start(), m.end(), b)]
            taken.append(m.span())
    num_range = re.search(r"\bdu\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+au\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", masked)
    cands = []
    for rx, kind in ((DATE_TXT, "txt"), (DATE_NUM, "num")):
        for mm in rx.finditer(masked):
            if any(mm.start() < e and s < mm.end() for s, e in taken):
                continue
            if kind == "txt":
                d, mo, y = mm.groups()
                dt = _to_date(int(y or year), MONTHS[mo], 1 if d == "1er" else int(d))
            else:
                g = mm.groups()
                if g[0]:
                    dt = _to_date(int(g[0]), int(g[1]), int(g[2]))
                elif g[3]:
                    y = int(g[5]) if g[5] else year
                    dt = _to_date(y + 2000 if y < 100 else y, int(g[4]), int(g[3]))
                else:
                    y = int(g[8])
                    dt = _to_date(y + 2000 if y < 100 else y, int(g[7]), int(g[6]))
            if dt:
                cands.append((mm.start(), mm.end(), dt))
    cands.sort()
    last_end = -1
    for s, e, dt in cands:
        if s >= last_end:
            found.append((s, e, dt))
            last_end = e
    found.sort()
    if rng is None and found and re.search(r"\bdepuis le\b", masked):
        rng = (found[0][2], date(2999, 12, 31))  # open-ended: "depuis le 10 octobre"
    if num_range and rng is None:
        ds = [d for _, _, d in found]
        if len(ds) >= 2:
            rng = (ds[0], ds[1])
    return found, rng


def _state_from(word: str):
    w = word
    for _ in range(3):
        if w in STATES:
            return STATES[w]
        w = w[:-1] if w.endswith(("s", "e")) else w
    return STATES.get(w)


def _sentences(text: str) -> list[tuple[int, int]]:
    """Sentence spans. Abbreviation dots are swapped for a same-length character before splitting."""
    protected = re.sub(r"\b(M|Mme|Mlle|Mr|Dr|Me|St)\.", lambda m: m.group()[:-1] + "․", text)
    spans, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+|\n+", protected):
        if protected[start:m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if protected[start:].strip():
        spans.append((start, len(protected)))
    return spans


def analyze_text(text: str, pv_id: str, witness: str, default_year: int) -> dict:
    """Return {"entities": {...}, "facts": [...]} for one PV."""
    folded = fold(text)
    years = Counter(re.findall(r"\b(19\d{2}|20\d{2})\b", folded))
    year = int(years.most_common(1)[0][0]) if years else default_year

    doc = get_nlp()(text)
    spacy_ents = [(e.start_char, e.end_char, e.label_, e.text) for e in doc.ents if e.label_ in ("PER", "LOC")]

    persons: dict[str, str] = {}
    places: dict[str, str] = {}
    dates_raw: list[tuple[str, str]] = []
    amounts: dict[float, str] = {}
    times: list[str] = []
    facts: list[dict] = []

    for s, e in _sentences(text):
        sent, f = text[s:e], folded[s:e]
        s_persons = []
        s_places = []
        for a, b, label, raw in spacy_ents:
            if s <= a and b <= e:
                if label == "PER":
                    name = clean_person(raw)
                    if name and person_key(name):
                        s_persons.append(name)
                else:
                    name = clean_person(raw)
                    s_places.append(CITIES.get(fold(name), name))
        for tm in TITLED_PERSON.finditer(sent):  # spaCy often misses a lone "M. Dupont"
            s_persons.append(tm.group(1))
        for pm in PLACE_RE.finditer(f):
            key = pm.group(1)
            s_places.append(CITIES.get(key, GENERIC_PLACES.get(key)))
        s_places = list(dict.fromkeys(p for p in s_places if p))
        by_key: dict[str, str] = {}
        for name in s_persons:
            key = person_key(name)
            if len(name) > len(by_key.get(key, "")):
                by_key[key] = name
        s_persons = list(by_key.values())
        for p in s_persons:
            persons.setdefault(person_key(p), p)
        for p in s_places:
            places.setdefault(fold(p), p)

        found, rng = find_dates(f, year)
        for a, b, dt in found:
            dates_raw.append((sent[a:b], dt.isoformat()))
        for am in AMOUNT_RE.finditer(f):
            whole = re.sub(r"[   .]", "", am.group(1))
            val = float(whole + ("." + am.group(2) if am.group(2) else ""))
            amounts.setdefault(val, sent[am.start():am.end()].strip())
        for tm in TIME_RE.finditer(IP_RE.sub(lambda m: " " * len(m.group()), f)):
            if re.search(r"\ben\s*$", f[:tm.start()]):  # "en 1h" is a duration, not a time of day
                continue
            h, mi = (tm.group(1), tm.group(2)) if tm.group(1) else (tm.group(3), tm.group(4))
            times.append(f"{int(h):02d}:{mi or '00'}")

        if SKIP_FACTS.match(f):
            continue
        kinds = [k for k, rx in KIND_PATTERNS.items() if rx.search(f)]
        if "click" in kinds and "receive" in kinds:
            kinds.remove("receive")
        if "compromise" in kinds and "action" in kinds:
            kinds.remove("action")
        first = bool(FIRST_PERSON.search(f))
        states = []
        for sm in STATE_RE.finditer(f):
            st = _state_from(sm.group(3))
            if st:
                value = st[1] != bool(sm.group(2))
                states.append([sm.group(1), st[0], value])
        travel = None
        tm = TRAVEL_RE.search(f)
        if tm:
            amount = NUM_WORDS.get(tm.group(3)) or float(tm.group(3).replace(",", "."))
            hours = amount / 60 if tm.group(4).startswith("min") else float(amount)
            if tm.group(5) and not tm.group(4).startswith("min"):
                hours += int(tm.group(5)) / 60
            mode = "avion" if "avion" in f else "train" if re.search(r"\b(train|tgv)\b", f) else \
                "voiture" if re.search(r"\b(voiture|route)\b", f) else "sol"
            travel = {"from": tm.group(1), "to": tm.group(2), "hours": hours, "mode": mode}
        weekdays = [WEEKDAYS[w] for w in WEEKDAY_RX.findall(f)]
        if not (kinds or states or travel):
            continue
        facts.append({
            "pv": pv_id, "witness": witness, "text": re.sub(r"\s+", " ", sent).strip()[:240],
            "persons": s_persons, "places": s_places, "first_person": first,
            "dates": sorted({d.isoformat() for _, _, d in found}),
            "range": [rng[0].isoformat(), rng[1].isoformat()] if rng else None,
            "weekdays": weekdays, "kinds": kinds, "states": states, "travel": travel,
        })

    uniq_dates = list(dict.fromkeys(dates_raw))
    entities = {
        "personnes": list(persons.values()),
        "lieux": list(places.values()),
        "dates": [r for r, _ in uniq_dates],
        "dates_iso": sorted({i for _, i in uniq_dates}),
        "montants": [raw for raw in amounts.values()],
        "montants_valeurs": sorted(amounts),
        "heures": list(dict.fromkeys(times)),
    }
    return {"entities": entities, "facts": facts}
