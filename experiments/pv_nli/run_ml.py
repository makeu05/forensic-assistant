"""Experiment: can a French NLI model find factual contradictions between witness statements?

Run with the experiment environment (torch, transformers, sentence-transformers, scikit-learn):
    python experiments/pv_nli/run_ml.py cmarkea/distilcamembert-base-nli
    python experiments/pv_nli/run_ml.py MoritzLaurer/mDeBERTa-v3-base-mnli-xnli

For every sentence pair, the model gives the probability that the two sentences contradict each other,
in both directions. This script writes the raw scores to results/<model>.json; compare.py picks thresholds
and does the evaluation, so the scoring step (slow) and the analysis (fast) are separate.
It also embeds the sentences of each PV pair, to test whether similarity can pre-select pairs to check.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

HERE = Path(__file__).resolve().parent
EMBEDDER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH = 16


class Nli:
    def __init__(self, name: str):
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForSequenceClassification.from_pretrained(name).eval()
        labels = {int(i): l.lower() for i, l in self.model.config.id2label.items()}
        self.contra = next(i for i, l in labels.items() if l.startswith("contra"))
        self.labels = labels

    @torch.no_grad()
    def p_contradiction(self, premises: list[str], hypotheses: list[str]) -> list[float]:
        out = []
        for i in range(0, len(premises), BATCH):
            enc = self.tok(premises[i:i + BATCH], hypotheses[i:i + BATCH], return_tensors="pt", padding=True,
                           truncation=True, max_length=128)
            probs = torch.softmax(self.model(**enc).logits, dim=-1)
            out += probs[:, self.contra].tolist()
        return out


def main(name: str) -> None:
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    pv_pairs = json.loads((HERE / "pv_pairs.json").read_text(encoding="utf-8"))["pv_pairs"]
    torch.set_num_threads(max(1, torch.get_num_threads()))

    t0 = time.perf_counter()
    nli = Nli(name)
    load_s = time.perf_counter() - t0
    print(f"{name}: loaded in {load_s:.1f}s, labels {nli.labels}")

    # 1. labelled statement pairs, both directions
    a, b = [p["a"] for p in pairs], [p["b"] for p in pairs]
    t0 = time.perf_counter()
    ab = nli.p_contradiction(a, b)
    ba = nli.p_contradiction(b, a)
    pair_s = time.perf_counter() - t0
    pair_scores = {p["id"]: {"ab": x, "ba": y} for p, x, y in zip(pairs, ab, ba)}
    ms_per_call = pair_s / (2 * len(pairs)) * 1000
    print(f"  scored {len(pairs)} pairs both ways in {pair_s:.1f}s ({ms_per_call:.0f} ms per call)")

    # 2. full PV pairs: every cross sentence pair, both directions, plus embedding similarity
    embedder = SentenceTransformer(EMBEDDER)
    pv_out = {}
    t0 = time.perf_counter()
    for case in pv_pairs:
        sa, sb = case["a"]["sentences"], case["b"]["sentences"]
        ea = embedder.encode(sa, normalize_embeddings=True)
        eb = embedder.encode(sb, normalize_embeddings=True)
        sim = (ea @ eb.T).tolist()
        idx = [(i, j) for i in range(len(sa)) for j in range(len(sb))]
        fwd = nli.p_contradiction([sa[i] for i, _ in idx], [sb[j] for _, j in idx])
        rev = nli.p_contradiction([sb[j] for _, j in idx], [sa[i] for i, _ in idx])
        pv_out[case["id"]] = {"cells": [{"i": i, "j": j, "ab": f, "ba": r, "sim": sim[i][j]}
                                        for (i, j), f, r in zip(idx, fwd, rev)]}
    pv_s = time.perf_counter() - t0
    n_cells = sum(len(v["cells"]) for v in pv_out.values())
    print(f"  scored {n_cells} PV sentence pairs (both ways) + embeddings in {pv_s:.1f}s")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    slug = name.replace("/", "__")
    (out / f"{slug}.json").write_text(json.dumps({
        "model": name, "embedder": EMBEDDER, "load_seconds": load_s, "ms_per_nli_call": ms_per_call,
        "torch_threads": torch.get_num_threads(), "pairs": pair_scores, "pv": pv_out,
    }, indent=1), encoding="utf-8")
    print(f"  wrote results/{slug}.json")
    del np  # numpy is only needed by the embedder


if __name__ == "__main__":
    main(sys.argv[1])
