# Can a language model find contradictions between witness statements?

An experiment run before putting any machine learning into Locard. The question: the current rules only catch a few phrasings of a contradiction ("la porte était ouverte" / "fermée"). Would a French natural language inference (NLI) model catch more, at what cost, and with how many false alarms?

## Short answer

**Yes, partly, as a clearly labelled suggestion for the expert, with one small model.** It finds a share of what the rules cannot (0 of 14 planted contradictions for the rules, 6 of 14 for the model at a strict setting) with few false suggestions. It is not reliable enough to be a finding: it cannot tell a real contradiction from a pair that only looks contradictory (different time, different person, different object). So Locard shows its output as "suggestions to verify", separate from the rule-based inconsistencies and outside the coherence score.

## Method

- **Data** (synthetic, written by hand, see the caveat below)
  - `pairs.json`: 100 statement pairs, 50 contradictions of 8 kinds (state, action, quantity, identity, place, time, knowledge, presence) and 50 compatible pairs: 10 paraphrases, 10 unrelated, 10 complementary, and **20 hard negatives** that look contradictory but are compatible.
  - `pv_pairs.json`: 10 pairs of whole witness statements, with 14 planted contradictions and 3 control pairs that contain none. This is the realistic test: false alarms per case.
- **Models** (all permissive licences)
  - `cmarkea/distilcamembert-base-nli`: French, 272 MB, MIT.
  - `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: multilingual, 558 MB, MIT.
  - `paraphrase-multilingual-MiniLM-L12-v2` (Apache 2.0): sentence embeddings, to test whether similarity can pick which pairs to check.
  - Left out: `BaptisteDoyen/camembert-base-xnli`, which declares no licence.
- **Protocol**: the statement pairs are split by id into a DEV half and a TEST half. The decision threshold is chosen on DEV only (highest recall with precision of at least 80%) and results are reported on TEST, with 95% Wilson intervals. The whole-statement test then applies that threshold to unseen texts.
- **Baseline**: the current rules (`app/modules/pv`) on exactly the same data.
- **Hardware**: a laptop CPU (Intel i5-8300H, 4 threads used), no GPU.

## Results

### Isolated statement pairs (TEST half: 50 pairs, 25 contradictions)

| | Rules today | DistilCamemBERT | mDeBERTa |
|---|---|---|---|
| Recall | **8%** (2 of 25) | 56% (37 to 73) | 100% (87 to 100) |
| Precision | n/a (1 false alarm) | 67% (45 to 83) | 86% (69 to 95) |
| ROC AUC, all 100 pairs | n/a | 0.78 | 0.94 |
| Speed per sentence pair | instant | **16 ms** | **755 ms** |
| Hard negatives wrongly flagged (of 20) | n/a | 10 | 10 |

mDeBERTa separates the classes much better on isolated pairs. Both models flag half of the hard negatives: the model cannot see that "fermée à 8h" and "ouverte à 18h" are compatible. Easy compatible pairs (paraphrases, unrelated sentences) are almost never flagged by DistilCamemBERT.

### Whole statements (10 PV pairs, 14 planted contradictions)

| Way of using the models | Real ones found | False suggestions |
|---|---|---|
| Rules today | 0 of 14 | 0 |
| mDeBERTa on every pair, fixed threshold | 11 of 14 | 48 (every control case had some) |
| DistilCamemBERT on every pair, fixed threshold | 7 of 14 | 4 |
| Top 3 per case, DistilCamemBERT, shared-word candidates | 9 of 14 | 21 |
| Top 3 per case, mDeBERTa, same candidates | 9 of 14 | 21 |
| Top 3 per case, both models combined (lower or average) | 9 of 14 | 21 |
| Cascade: fast model shortlists, slow model re-checks | 9 of 14 | 21 (and 45 to 68 s instead of 1.5 s) |
| **Cap 3 per case, minimum score 0.95, DistilCamemBERT** | **6 of 14** | **2** (1 control case) |

Reading it: on isolated pairs the slow model looks better, but on whole statements it gives the same ranking as the fast one, and its high-confidence scores are saturated (many wrong pairs at 1.00), which is why a fixed threshold produced 48 false alarms. Combining the two did not help. The second model costs 47 times more time for no gain in the realistic setting.

### Which pairs to check

Checking every sentence pair of two statements is quadratic. Pre-selecting by similarity:

| Candidate selection | Real pairs kept | Pairs to check (of 192) |
|---|---|---|
| Embeddings, top 2 per sentence | 7 of 14 | 50 |
| Shared spaCy lemmas (needs the full pipeline) | 11 of 14 | 40 |
| **Shared 5-letter word prefixes (no extra model)** | **10 of 14** | **45** |

Embeddings lose half of the real pairs: two sentences can contradict each other with little surface similarity ("je suis la seule personne à avoir accès" / "tout le service utilise le même identifiant"). Shared words are cheaper and better, and need no third model.

## Decision

- **Integrate one model: DistilCamemBERT.** Fast (16 ms), French, MIT, 272 MB. mDeBERTa stays out by default: slower, no gain on whole statements. It can be selected with `LOCARD_NLI_MODEL` for anyone who wants to try it.
- **Candidates by shared word prefixes**, capped per pair of statements. No embedding model.
- **Show at most 3 suggestions per pair of statements, only at 0.95 or above**, labelled as automatic suggestions to verify, never mixed with the rule-based findings and never counted in the coherence score.
- **Run it as a background step**, not inside the 3-second PV analysis: a long case means thousands of sentence pairs.

## Caveats you should know

1. **The data is synthetic and written by the person who built the rules.** It compares approaches fairly but cannot prove real-world accuracy. The hard negatives are mine; real testimony has irony, vagueness and mistakes that I did not write.
2. **The sample is small**: 25 contradictions in the TEST half. The intervals above are wide on purpose.
3. **The operating point (cap 3, minimum 0.95) was read off the same 10 cases it is reported on.** It agrees with the threshold (0.96) chosen independently on the DEV half, which is why I trust it more, but a fair figure needs new statements.
4. **Recall is modest**: about 43% of planted contradictions at that setting. The model will miss most of what it is not confident about.
5. **French only.** Nothing was tested in another language.

## Reproduce

```powershell
# the experiment environment (kept outside the project)
python -m venv mlvenv
mlvenv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
mlvenv\Scripts\python -m pip install transformers sentence-transformers scikit-learn

.venv\Scripts\python experiments/pv_nli/baseline_rules.py            # the rules on the same data
mlvenv\Scripts\python experiments/pv_nli/run_ml.py cmarkea/distilcamembert-base-nli
mlvenv\Scripts\python experiments/pv_nli/run_ml.py MoritzLaurer/mDeBERTa-v3-base-mnli-xnli
.venv\Scripts\python experiments/pv_nli/compare.py                  # statement pairs and whole statements
.venv\Scripts\python experiments/pv_nli/analyze_design.py           # candidates, ranking, cascade, caps
```

The scoring step is slow (the first run downloads the models); the two analysis scripts replay the stored scores in seconds. Raw scores are in `results/`.
