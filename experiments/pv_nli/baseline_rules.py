"""Baseline: what the current rules (app/modules/pv) find on the experiment data.

Run with the project's own environment:   .venv\\Scripts\\python experiments/pv_nli/baseline_rules.py
It writes results/rules.json, which compare.py reads next to the model results.

For a statement pair, each sentence becomes a one-sentence PV and the rules run on both: a pair counts as
"contradiction" if the rules report any inconsistency. For a statement pair of full PVs, the rules run on the
whole text and each reported inconsistency is mapped back to the sentence pair it quotes.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from app.modules.pv.nlp import analyze_text  # noqa: E402
from app.modules.pv.rules import detect  # noqa: E402


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def facts_of(text: str, pv_id: str, witness: str) -> list[dict]:
    return analyze_text(text, pv_id, witness, 2025)["facts"]


def main() -> None:
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    pv_pairs = json.loads((HERE / "pv_pairs.json").read_text(encoding="utf-8"))["pv_pairs"]

    pair_pred = {}
    for p in pairs:
        facts = facts_of(p["a"], "a", "Témoin A") + facts_of(p["b"], "b", "Témoin B")
        found = detect(facts)
        pair_pred[p["id"]] = {"contradiction": bool(found), "rules": sorted({i["rule"] for i in found})}

    pv_pred = {}
    for case in pv_pairs:
        a_sent, b_sent = case["a"]["sentences"], case["b"]["sentences"]
        facts = facts_of(" ".join(a_sent), "a", case["a"]["witness"]) + facts_of(" ".join(b_sent), "b", case["b"]["witness"])
        index_a = {norm(s): i for i, s in enumerate(a_sent)}
        index_b = {norm(s): j for j, s in enumerate(b_sent)}
        flagged = []
        for inc in detect(facts):
            ev = {e["pv_id"]: norm(e["excerpt"]) for e in inc["evidence"]}
            if "a" in ev and "b" in ev and ev["a"] in index_a and ev["b"] in index_b:
                flagged.append([index_a[ev["a"]], index_b[ev["b"]]])
            else:
                flagged.append(None)  # inconsistency inside one PV or not mappable: counted as unmapped
        pv_pred[case["id"]] = {"flagged": flagged}

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "rules.json").write_text(json.dumps({"pairs": pair_pred, "pv": pv_pred}, ensure_ascii=False, indent=1), encoding="utf-8")
    hit = sum(v["contradiction"] for v in pair_pred.values())
    print(f"rules flagged {hit} of {len(pairs)} statement pairs; wrote results/rules.json")


if __name__ == "__main__":
    main()
