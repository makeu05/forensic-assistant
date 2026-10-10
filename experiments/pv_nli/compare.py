"""Compare the current rules with NLI models on the experiment data. Pure analysis, runs in seconds.

    .venv\\Scripts\\python experiments/pv_nli/compare.py

Method, so the numbers are not flattering by construction:
- The 100 statement pairs are split by id: odd ids are the DEV half, even ids the TEST half.
- The decision threshold is chosen on DEV only (highest recall with precision >= 0.80, else best F1).
- Precision and recall are reported on TEST only, with a 95% Wilson interval (50 pairs cannot support more).
- The PV-pair test then uses that same threshold on unseen texts and counts false alarms per case.
"""
import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
TARGET_PRECISION = 0.80
RETRIEVAL_SETTINGS = [(1, 0.30), (2, 0.30), (3, 0.30), (2, 0.45)]  # (top-k per sentence, minimum similarity)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def interval(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{pct(k / n if n else 0)} ({pct(lo)} to {pct(hi)})"


def choose_threshold(scores: list[float], y: list[bool]) -> tuple[float, str]:
    best_recall, best_f1 = None, None
    for t in np.arange(0.02, 1.0, 0.01):
        pred = [s >= t for s in scores]
        tp = sum(p and a for p, a in zip(pred, y))
        fp = sum(p and not a for p, a in zip(pred, y))
        fn = sum((not p) and a for p, a in zip(pred, y))
        p, r, f = prf(tp, fp, fn)
        if p >= TARGET_PRECISION and tp and (best_recall is None or r > best_recall[0]):
            best_recall = (r, t)
        if best_f1 is None or f > best_f1[0]:
            best_f1 = (f, t)
    if best_recall:
        return float(best_recall[1]), f"recall-maximising with precision >= {TARGET_PRECISION:.0%} on DEV"
    return float(best_f1[1]), f"best F1 on DEV (precision {TARGET_PRECISION:.0%} was not reachable)"


def candidates(cells: list[dict], k: int, min_sim: float) -> set[tuple[int, int]]:
    """Pairs worth checking: for every sentence, its k most similar sentences in the other PV."""
    out = set()
    by_i, by_j = {}, {}
    for c in cells:
        by_i.setdefault(c["i"], []).append(c)
        by_j.setdefault(c["j"], []).append(c)
    for group in list(by_i.values()) + list(by_j.values()):
        for c in sorted(group, key=lambda c: -c["sim"])[:k]:
            if c["sim"] >= min_sim:
                out.add((c["i"], c["j"]))
    return out


def evaluate_model(path: Path, pairs: list[dict], pv_cases: list[dict], rules: dict, lines: list[str]) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data["model"]
    y_all = {p["id"]: p["label"] == "contradiction" for p in pairs}
    dev = [p for p in pairs if p["id"] % 2 == 1]
    test = [p for p in pairs if p["id"] % 2 == 0]
    lines.append(f"\n## {name}\n")
    lines.append(f"Speed: {data['ms_per_nli_call']:.0f} ms per sentence pair on this CPU ({data['torch_threads']} threads), "
                 f"model loads in {data['load_seconds']:.1f} s.\n")

    summary = {"model": name}
    for agg, fn in (("max of both directions", max), ("mean of both directions", lambda a, b: (a + b) / 2)):
        score = {p["id"]: fn(data["pairs"][str(p["id"])]["ab"], data["pairs"][str(p["id"])]["ba"]) for p in pairs}
        tau, why = choose_threshold([score[p["id"]] for p in dev], [y_all[p["id"]] for p in dev])
        tp = sum(score[p["id"]] >= tau and y_all[p["id"]] for p in test)
        fp = sum(score[p["id"]] >= tau and not y_all[p["id"]] for p in test)
        fn_ = sum(score[p["id"]] < tau and y_all[p["id"]] for p in test)
        n_pos, n_flag = tp + fn_, tp + fp
        auc = roc_auc_score([y_all[p["id"]] for p in pairs], [score[p["id"]] for p in pairs])
        ap = average_precision_score([y_all[p["id"]] for p in pairs], [score[p["id"]] for p in pairs])
        lines.append(f"### Statement pairs, score = {agg}\n")
        lines.append(f"Threshold {tau:.2f} ({why}). Threshold-free quality on all 100 pairs: ROC AUC {auc:.2f}, average precision {ap:.2f}.\n")
        lines.append(f"On the TEST half ({len(test)} pairs, {n_pos} contradictions): "
                     f"recall {interval(tp, n_pos)}, precision {interval(tp, n_flag)}, {fp} false alarms.\n")
        if agg.startswith("max"):
            summary.update({"tau": tau, "score": score, "auc": auc, "ap": ap, "test_tp": tp, "test_fp": fp, "test_pos": n_pos})
            kinds = {}
            for p in pairs:
                kinds.setdefault((p["label"], p["kind"].split("-")[0] if p["kind"].startswith("hard") else p["kind"], p["kind"].startswith("hard")), []).append(p)
            lines.append("| Kind of pair | Pairs | Flagged at the threshold |")
            lines.append("|---|---|---|")
            for (label, kind, hard), group in sorted(kinds.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1])):
                hit = sum(score[p["id"]] >= tau for p in group)
                shown = ("hard negative: " + kind.replace("hard", "").strip("-") if hard else kind)
                what = "contradiction" if label == "contradiction" else "compatible"
                lines.append(f"| {what}, {shown if shown else 'hard'} | {len(group)} | {hit} ({pct(hit / len(group))}) |")
            lines.append("")
            hard = [p for p in pairs if p["kind"].startswith("hard")]
            fp_hard = sum(score[p["id"]] >= tau for p in hard)
            summary["hard_fp"], summary["hard_n"] = fp_hard, len(hard)
            worst = sorted([p for p in pairs if not y_all[p["id"]]], key=lambda p: -score[p["id"]])[:3]
            missed = sorted([p for p in pairs if y_all[p["id"]]], key=lambda p: score[p["id"]])[:3]
            lines.append("Highest-scoring COMPATIBLE pairs (false alarms):")
            for p in worst:
                lines.append(f"- {score[p['id']]:.2f}: \"{p['a']}\" / \"{p['b']}\" ({p['kind']})")
            lines.append("\nLowest-scoring CONTRADICTIONS (missed):")
            for p in missed:
                lines.append(f"- {score[p['id']]:.2f}: \"{p['a']}\" / \"{p['b']}\" ({p['kind']})")
            lines.append("")

    tau, score = summary["tau"], summary["score"]
    # rules on the same TEST half, for a like-for-like comparison
    r_tp = sum(rules["pairs"][str(p["id"])]["contradiction"] and y_all[p["id"]] for p in test)
    r_fp = sum(rules["pairs"][str(p["id"])]["contradiction"] and not y_all[p["id"]] for p in test)
    n_pos = sum(y_all[p["id"]] for p in test)
    lines.append(f"Current rules on the same TEST half: recall {interval(r_tp, n_pos)}, {r_fp} false alarms.\n")
    summary.update({"rules_tp": r_tp, "rules_fp": r_fp})

    # whole PV pairs
    lines.append("### Whole statements (10 PV pairs, 14 planted contradictions, 3 control pairs), same threshold\n")
    lines.append("| Strategy | Found | False alarms | False alarms per PV pair | Control pairs with a false alarm |")
    lines.append("|---|---|---|---|---|")
    planted_total = sum(len(c["planted"]) for c in pv_cases)
    controls = [c["id"] for c in pv_cases if not c["planted"]]

    def run(label: str, chooser) -> dict:
        found = fa = 0
        ctrl = 0
        per_case = {}
        for c in pv_cases:
            cells = data["pv"][c["id"]]["cells"]
            chosen = chooser(cells)
            flagged = {(x["i"], x["j"]) for x in cells if (x["i"], x["j"]) in chosen and max(x["ab"], x["ba"]) >= tau}
            planted = {tuple(p) for p in c["planted"]}
            found += len(flagged & planted)
            fa += len(flagged - planted)
            per_case[c["id"]] = sorted(flagged - planted)
            if c["id"] in controls and flagged - planted:
                ctrl += 1
        lines.append(f"| {label} | {found} of {planted_total} | {fa} | {fa / len(pv_cases):.1f} | {ctrl} of {len(controls)} |")
        return {"found": found, "fa": fa, "ctrl": ctrl, "per_case": per_case}

    out = {"all": run("NLI on every sentence pair", lambda cells: {(x["i"], x["j"]) for x in cells})}
    for k, s in RETRIEVAL_SETTINGS:
        out[(k, s)] = run(f"embeddings pick top-{k} per sentence (similarity >= {s}), then NLI", lambda cells, k=k, s=s: candidates(cells, k, s))
        kept = tot = 0
        n_cand = 0
        for c in pv_cases:
            cand = candidates(data["pv"][c["id"]]["cells"], k, s)
            n_cand += len(cand)
            for p in c["planted"]:
                tot += 1
                kept += tuple(p) in cand
        lines.append(f"|   (the picker keeps {kept} of {tot} planted pairs, {n_cand} pairs to check instead of {sum(len(c['a']['sentences']) * len(c['b']['sentences']) for c in pv_cases)}) | | | | |")
    r_found = r_fa = 0
    for c in pv_cases:
        flagged = {tuple(f) for f in rules["pv"][c["id"]]["flagged"] if f}
        planted = {tuple(p) for p in c["planted"]}
        r_found += len(flagged & planted)
        r_fa += len(flagged - planted)
    lines.append(f"| Current rules | {r_found} of {planted_total} | {r_fa} | {r_fa / len(pv_cases):.1f} | n/a |")
    lines.append("")
    summary["pv"] = {str(k): v for k, v in out.items()}
    return summary


def main() -> None:
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    pv_cases = json.loads((HERE / "pv_pairs.json").read_text(encoding="utf-8"))["pv_pairs"]
    rules = json.loads((RES / "rules.json").read_text(encoding="utf-8"))
    lines = ["# PV contradiction experiment: results", "",
             "Generated by `compare.py`. Data: 100 hand-written statement pairs (50 contradictions) and 10 PV pairs, "
             "all synthetic and written by the same person who built the rules, so read the numbers as a comparison "
             "between approaches, not as real-world accuracy."]
    summaries = []
    for path in sorted(RES.glob("*.json")):
        if path.name in ("rules.json", "summary.json"):
            continue
        summaries.append(evaluate_model(path, pairs, pv_cases, rules, lines))
    text = "\n".join(lines)
    (RES / "report.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
