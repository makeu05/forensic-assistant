"""Which way of using the models is practical? Offline analysis of the scores already collected.

    .venv\\Scripts\\python experiments/pv_nli/analyze_design.py

Everything here replays stored scores, so any design can be tried without running a model again.
1. Ranking: instead of a threshold, show the k best-scoring pairs of each case. Recall@k and false alarms@k.
2. Cascade: a fast model scores every candidate, the slow one only re-checks the fast model's shortlist.
3. Candidates: which sentence pairs are worth checking at all (shared words versus embeddings).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

import spacy  # noqa: E402
from app.modules.pv.nlp import fold  # noqa: E402

RES = HERE / "results"
FAST = "cmarkea__distilcamembert-base-nli"
SLOW = "MoritzLaurer__mDeBERTa-v3-base-mnli-xnli"
PV = json.loads((HERE / "pv_pairs.json").read_text(encoding="utf-8"))["pv_pairs"]
DATA = {m: json.loads((RES / f"{m}.json").read_text(encoding="utf-8")) for m in (FAST, SLOW)}
STOP = {"être", "avoir", "faire", "aller", "pouvoir", "vouloir", "devoir", "dire", "rester", "venir"}


def cells(model: str, case_id: str) -> dict[tuple[int, int], dict]:
    return {(c["i"], c["j"]): c for c in DATA[model]["pv"][case_id]["cells"]}


def score(c: dict, how: str) -> float:
    return max(c["ab"], c["ba"]) if how == "max" else (c["ab"] + c["ba"]) / 2


def content_lemmas(doc) -> set[str]:
    return {t.lemma_.lower() for t in doc if t.pos_ in ("NOUN", "PROPN", "VERB", "NUM") and t.lemma_.lower() not in STOP and len(t.lemma_) > 2}


def lexical_candidates(case: dict, nlp) -> set[tuple[int, int]]:
    a = [content_lemmas(nlp(s)) for s in case["a"]["sentences"]]
    b = [content_lemmas(nlp(s)) for s in case["b"]["sentences"]]
    return {(i, j) for i, x in enumerate(a) for j, y in enumerate(b) if x & y}


FUNCTION_WORDS = set("""dans avec pour cette cette ainsi alors apres avant aucun aucune autre comme depuis donc elle elles entre
encore etait etaient etais etre avait avaient avoir fait faire leur leurs mais meme moins nous plus puis quand sans sont sous
tout tous toute toutes tres vers vous votre notre mon mes son ses nos aussi cela celui celle ceux cette ete suis ont
qui que quoi dont lors depuis jusqu ensuite pendant seul seule seulement jamais toujours deja encore rien personne""".split())


def prefix_tokens(text: str, n: int = 5) -> set[str]:
    """Light stand-in for lemmas: accent-free lowercase words of 5+ letters, cut to their first n letters."""
    words = re.findall(r"[a-z0-9]+", fold(text))
    return {w[:n] for w in words if (len(w) >= 5 or w.isdigit()) and w not in FUNCTION_WORDS}


def prefix_candidates(case: dict, n: int = 5) -> set[tuple[int, int]]:
    a = [prefix_tokens(s, n) for s in case["a"]["sentences"]]
    b = [prefix_tokens(s, n) for s in case["b"]["sentences"]]
    return {(i, j) for i, x in enumerate(a) for j, y in enumerate(b) if x & y}


def embedding_candidates(case: dict, k: int = 2, min_sim: float = 0.30) -> set[tuple[int, int]]:
    cs = DATA[FAST]["pv"][case["id"]]["cells"]
    out = set()
    for key in ("i", "j"):
        groups = {}
        for c in cs:
            groups.setdefault(c[key], []).append(c)
        for g in groups.values():
            for c in sorted(g, key=lambda c: -c["sim"])[:k]:
                if c["sim"] >= min_sim:
                    out.add((c["i"], c["j"]))
    return out


def total_cells() -> int:
    return sum(len(c["a"]["sentences"]) * len(c["b"]["sentences"]) for c in PV)


def rank_eval(label: str, pick, ks=(1, 3, 5)) -> None:
    """pick(case) -> list of ((i, j), score) for the case, any order."""
    planted_total = sum(len(c["planted"]) for c in PV)
    row = []
    for k in ks:
        found = fa = 0
        for c in PV:
            top = sorted(pick(c), key=lambda x: -x[1])[:k]
            planted = {tuple(p) for p in c["planted"]}
            found += sum(p in planted for p, _ in top)
            fa += sum(p not in planted for p, _ in top)
        row.append(f"top-{k}: {found}/{planted_total} found, {fa} false")
    print(f"  {label:<58} " + " | ".join(row))


def main() -> None:
    nlp = spacy.load("fr_core_news_lg")  # the full pipeline (the app's own excludes the lemmatizer)
    spacy_lex = {c["id"]: lexical_candidates(c, nlp) for c in PV}
    lex = {c["id"]: prefix_candidates(c) for c in PV}
    emb = {c["id"]: embedding_candidates(c) for c in PV}
    planted_total = sum(len(c["planted"]) for c in PV)

    print(f"{planted_total} planted contradictions in {len(PV)} PV pairs, {total_cells()} sentence pairs in all\n")
    print("== 3. Candidate selection: which pairs are worth checking ==")
    for name, cand in (("shared spaCy lemmas (needs the full pipeline)", spacy_lex), ("shared 5-letter word prefixes (no extra model)", lex), ("embeddings top-2, similarity >= 0.30", emb),
                       ("prefixes + embeddings together", {k: lex[k] | emb[k] for k in lex})):
        kept = sum(tuple(p) in cand[c["id"]] for c in PV for p in c["planted"])
        n = sum(len(v) for v in cand.values())
        print(f"  {name:<40} keeps {kept}/{planted_total} planted pairs, {n} of {total_cells()} pairs to check")
    missed = [(c["id"], p) for c in PV for p in c["planted"] if tuple(p) not in lex[c["id"]]]
    print(f"  pairs the prefix filter loses: {missed}\n")

    print("== 1. Ranking: the k best pairs per case, instead of a threshold ==")
    every = {c["id"]: [(k, 0) for k in cells(FAST, c["id"])] for c in PV}
    for model, short in ((FAST, "fast (DistilCamemBERT)"), (SLOW, "slow (mDeBERTa)")):
        for how in ("max", "mean"):
            rank_eval(f"{short}, {how}, all pairs", lambda c, m=model, h=how: [(k, score(v, h)) for k, v in cells(m, c["id"]).items()])
            rank_eval(f"{short}, {how}, shared-word candidates", lambda c, m=model, h=how: [(k, score(v, h)) for k, v in cells(m, c["id"]).items() if k in lex[c["id"]]])
    rank_eval("both models: the lower of the two (max), shared-word candidates",
              lambda c: [(k, min(score(cells(FAST, c["id"])[k], "max"), score(cells(SLOW, c["id"])[k], "max"))) for k in lex[c["id"]]])
    rank_eval("both models: average (max), shared-word candidates",
              lambda c: [(k, (score(cells(FAST, c["id"])[k], "max") + score(cells(SLOW, c["id"])[k], "max")) / 2) for k in lex[c["id"]]])
    del every

    print("\n== 2. Cascade: fast model shortlists n pairs, the slow model re-checks only those ==")
    for n in (3, 5, 8):
        def pick(c, n=n):
            fast = cells(FAST, c["id"])
            short = sorted(lex[c["id"]], key=lambda k: -score(fast[k], "max"))[:n]
            slow = cells(SLOW, c["id"])
            return [(k, score(slow[k], "max")) for k in short]
        rank_eval(f"fast shortlist of {n}, then slow ranks them", pick, ks=(1, 3))
        calls = sum(2 * min(n, len(lex[c["id"]])) for c in PV)
        print(f"     -> slow model calls for the 10 cases: {calls} (about {calls * DATA[SLOW]['ms_per_nli_call'] / 1000:.0f} s on this CPU)")
    print("\n== 4. What to show: a cap per case plus a minimum score (fast model, prefix candidates) ==")
    controls = [c["id"] for c in PV if not c["planted"]]
    print("  cap per case | minimum score | found | false suggestions | false in the 3 control cases | suggestions shown")
    for cap in (2, 3, 5):
        for floor in (0.0, 0.5, 0.8, 0.9, 0.95):
            found = fa = ctrl = shown = 0
            for c in PV:
                fast = cells(FAST, c["id"])
                top = sorted(((k, score(fast[k], "max")) for k in lex[c["id"]]), key=lambda x: -x[1])[:cap]
                top = [(k, v) for k, v in top if v >= floor]
                planted = {tuple(p) for p in c["planted"]}
                found += sum(k in planted for k, _ in top)
                bad = sum(k not in planted for k, _ in top)
                fa += bad
                shown += len(top)
                ctrl += bad if c["id"] in controls else 0
            print(f"  {cap:^12} | {floor:^13} | {found:>2}/{planted_total} | {fa:^17} | {ctrl:^28} | {shown}")
    fast_calls = sum(2 * len(lex[c["id"]]) for c in PV)
    print(f"  fast model on all shared-word candidates: {fast_calls} calls, about {fast_calls * DATA[FAST]['ms_per_nli_call'] / 1000:.1f} s for the 10 cases")


if __name__ == "__main__":
    main()
