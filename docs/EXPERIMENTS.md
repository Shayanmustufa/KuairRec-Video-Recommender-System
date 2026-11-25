# Experiment Log

## Day 4 — Training-only popularity baseline

- **Model ID:** `popularity-positive-event-count-v1`
- **Training signal:** count of training events with `watch_ratio > 2.0`
- **Candidates:** full 8,418-item eligible catalog minus training-seen items
- **Tie-break:** ascending `video_id`
- **Validation users:** 7,176 total; 6,761 metric-eligible; 415 without an
  eligible relevant candidate
- **Test usage:** none
- **Runtime:** 21.9996 seconds on Python 3.11.9 / Windows

| Metric | Result |
|---|---:|
| Recall@10 | 0.015693 |
| Recall@20 | 0.024042 |
| NDCG@10 | 0.016763 |
| NDCG@20 | 0.019448 |
| Precision@10 | 0.013637 |
| Precision@20 | 0.011914 |
| Hit Rate@10 | 0.099246 |
| Hit Rate@20 | 0.154119 |
| Catalog coverage@20 | 0.026372 (222 items) |
| All-user evaluation coverage | 0.942168 |

Primary ranking metrics average over users with at least one eligible relevant
validation item. Users without one are excluded from metric means and reported
through all-user evaluation coverage. Generated artifacts, predictions, exact
metrics, per-user examples, input hashes, and artifact hashes are under the
ignored `model/artifacts/` directory and reproduce with:

```powershell
python -m model.src.popularity
```

The low ranking and catalog-coverage results are retained as the honest global
baseline. They motivate Day 5 personalization but are not a reason to alter the
frozen target or validation protocol.

## Day 5 — Item-based collaborative filtering

- **Model ID:** `item-cf-cosine-v1`
- **Training graph:** distinct positive (`watch_ratio > 2.0`) training-only
  user–item edges
- **Preference strength:** maximum `log1p(watch_ratio)` per positive training
  user–item pair
- **Similarity:** implicit cosine with cooccurrence shrinkage
- **Score:** similarity-weighted mean of positive-history preference strengths
- **Candidates:** full 8,418-item catalog minus training-seen items
- **Tuning:** fixed validation-only grid on a seed-2026 sample of 1,000 eligible
  users; NDCG@10 primary, Recall@10 secondary
- **Selected configuration:** 5 neighbors, shrinkage 200
- **Test usage:** none
- **Runtime:** 35.7154 seconds on Python 3.11.9, NumPy 2.4.6, SciPy 1.17.1

| Metric | Item-CF | Popularity | Difference |
|---|---:|---:|---:|
| Recall@10 | 0.012228 | 0.015693 | -0.003465 |
| Recall@20 | 0.020438 | 0.024042 | -0.003604 |
| NDCG@10 | 0.015370 | 0.016763 | -0.001393 |
| NDCG@20 | 0.018089 | 0.019448 | -0.001359 |
| Precision@10 | 0.012868 | 0.013637 | -0.000769 |
| Precision@20 | 0.012461 | 0.011914 | +0.000547 |
| Hit Rate@10 | 0.108860 | 0.099246 | +0.009614 |
| Hit Rate@20 | 0.184292 | 0.154119 | +0.030173 |
| Catalog coverage@20 | 0.661796 (5,571 items) | 0.026372 (222 items) | +0.635424 |

Item-CF does not beat popularity on the primary Recall/NDCG metrics, so it is
not promoted as the best standalone ranker. It does improve Hit Rate and
catalog coverage substantially, showing a personalization/diversity benefit
that can be tested in the later validation-tuned hybrid. A plausible
interpretation is that global popularity captures strong common temporal
preferences, while the sparse five-neighbor model reaches many more niche
items but ranks fewer total held-out positives near the top. This interpretation
is validation evidence, not a causal claim.

The tuning grid was expanded twice because preliminary winners landed on search
boundaries. The final selected point is interior to the frozen 7×7 grid:
neighborhoods `{1, 3, 5, 10, 20, 50, 100}` and shrinkage
`{0, 10, 50, 100, 200, 500, 1000}`. Exact grid results, predictions, mappings,
model matrix, examples, and checksums are in ignored `model/artifacts/` files.

```powershell
python -m model.src.item_cf
```

## Day 6 — LightGCN debugging prototype

This run is a feasibility/debugging result, not the selected LightGCN model.
Initial hyperparameters were frozen before the run:

- Seed: `2026`
- Sample: 256 seeded validation-eligible users
- Graph: 22,724 distinct positive training-only edges and the full 8,418-item
  eligible catalog
- Embedding dimension: `32`
- Propagation layers: `2`
- Learning rate: `0.001`
- L2 regularization: `0.0001`
- Epochs: `10`
- Loss: Bayesian Personalized Ranking with one training-seen-safe negative per
  positive edge and epoch
- Device: CPU for deterministic debugging
- Test usage: none

Training remained finite and the loss decreased every epoch, from `0.691725`
to `0.689965`. All exported embeddings and validation scores are finite.

| Debug validation measure | Result |
|---|---:|
| Users | 256 total / 254 metric-eligible |
| Recall@10 | 0.000976 |
| Recall@20 | 0.003782 |
| NDCG@10 | 0.003404 |
| NDCG@20 | 0.003697 |
| Catalog coverage@20 | 0.323236 (2,721 items) |
| Runtime | 13.2809 seconds |

The small untuned prototype is weak on ranking metrics but passes the Day 6
feasibility gate: graph propagation, BPR optimization, full-catalog scoring,
seen-item filtering, checkpoint export, and deterministic validation all run
without numerical failure. Day 7 must evaluate allowed hyperparameters on
validation before comparing LightGCN with the frozen baselines.

```powershell
python -m model.src.lightgcn
```

## Day 7 — Validation-tuned LightGCN

Day 7 tested only the four permitted LightGCN parameters. A fixed eight-run
one-factor grid was evaluated on 1,024 seed-2026 validation-eligible users.
NDCG@10 was primary and Recall@10 secondary; lower-complexity settings broke
ties. The selected configuration was retrained on the complete training graph:

- Learning rate: `0.002`
- Propagation layers: `2`
- Embedding dimension: `32`
- Epochs: `15`
- L2 regularization: `0.0001` (fixed)
- Full graph: 7,176 users, 8,418 items, 598,971 distinct positive edges
- Hardware: NVIDIA RTX 4000 Ada Generation, 20 GiB
- Runtime: 123.7905 seconds
- Test usage: none

The full training loss remained finite and decreased from `0.692951` to
`0.684865`. Exported user/item embeddings and all scores are finite.

| Metric | LightGCN | Popularity | Item-CF |
|---|---:|---:|---:|
| Recall@10 | 0.008589 | 0.015693 | 0.012228 |
| Recall@20 | 0.015793 | 0.024042 | 0.020438 |
| NDCG@10 | 0.009279 | 0.016763 | 0.015370 |
| NDCG@20 | 0.012077 | 0.019448 | 0.018089 |
| Precision@10 | 0.007809 | 0.013637 | 0.012868 |
| Precision@20 | 0.008135 | 0.011914 | 0.012461 |
| Hit Rate@10 | 0.065819 | 0.099246 | 0.108860 |
| Hit Rate@20 | 0.124834 | 0.154119 | 0.184292 |
| Catalog coverage@20 | 0.570801 | 0.026372 | 0.661796 |

LightGCN is rejected as the selected standalone model because it trails both
frozen baselines on every ranking metric. Its coverage is much higher than
popularity but lower than Item-CF, so coverage does not justify promotion.
This is a stable negative result rather than a numerical failure: loss,
embeddings, scores, predictions, and checksums all passed verification.

Per the Phase 3 stop rule, Day 8 is not started automatically. Using a rejected
LightGCN component in a hybrid, changing the advanced-model scope, or proceeding
with a baseline-only hybrid requires an explicit scope decision. Test data
remains sealed.

```powershell
python -m model.src.lightgcn_tune
```

## Day 8 — Validation-tuned hybrid and ablations

The approved three-component search included popularity, Item-CF, and the
rejected standalone LightGCN signal, while explicitly allowing any component
to receive zero weight.

- Normalization: per-user min–max over unseen full-catalog candidates
- Grid: all 66 nonnegative weight triples in increments of 0.1 that sum to one
- Tuning users: 1,024 seed-2026 validation-eligible users
- Selection: NDCG@10 primary, Recall@10 secondary
- Selected weights: popularity `0.1`, Item-CF `0.9`, LightGCN `0.0`
- Test usage: none
- Runtime: 25.3569 seconds

| Metric | Hybrid | Popularity | Item-CF | LightGCN |
|---|---:|---:|---:|---:|
| Recall@10 | 0.014071 | 0.015693 | 0.012228 | 0.008589 |
| Recall@20 | 0.029101 | 0.024042 | 0.020438 | 0.015793 |
| NDCG@10 | 0.016448 | 0.016763 | 0.015370 | 0.009279 |
| NDCG@20 | 0.021916 | 0.019448 | 0.018089 | 0.012077 |
| Precision@10 | 0.013829 | 0.013637 | 0.012868 | 0.007809 |
| Precision@20 | 0.014931 | 0.011914 | 0.012461 | 0.008135 |
| Hit Rate@10 | 0.113888 | 0.099246 | 0.108860 | 0.065819 |
| Hit Rate@20 | 0.208697 | 0.154119 | 0.184292 | 0.124834 |
| Catalog coverage@20 | 0.622832 | 0.026372 | 0.661796 | 0.570801 |

The selected hybrid beats Item-CF on every reported ranking metric. Against
popularity it improves Recall@20, NDCG@20, Precision@10/20, Hit Rate@10/20,
and catalog coverage, but trails slightly on Recall@10 and NDCG@10. Therefore
it is retained as the validation-selected multi-objective candidate, not
claimed to dominate popularity universally.

The zero LightGCN weight is an important ablation result: after common
per-user normalization, no tested positive LightGCN contribution improved the
primary selection objective over the selected popularity + Item-CF pair. Best
pairwise and single-component results, along with all 66 combinations, are
saved in `hybrid_validation_metrics.json`.

```powershell
python -m model.src.hybrid
```

## Day 11 — Single controlled test pass

The Day 9 frozen hybrid was evaluated once after the Day 10 leakage audit
passed. Model selection was not reopened and no setting changed after viewing
test outcomes.

- Model: `hybrid-validation-selected-v1`
- Weights: 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN
- Seed: 2026
- Test users: 7,176 total; 6,255 metric-eligible; 921 without an eligible
  relevant candidate
- Runtime: 24.6569 seconds

| Metric | Controlled test |
|---|---:|
| Recall@10 | 0.012742 |
| Recall@20 | 0.025472 |
| NDCG@10 | 0.015098 |
| NDCG@20 | 0.019188 |
| Precision@10 | 0.012902 |
| Precision@20 | 0.013397 |
| Hit Rate@10 | 0.109033 |
| Hit Rate@20 | 0.198721 |
| Catalog coverage@20 | 0.638513 (5,375 items) |
| All-user evaluation coverage | 0.871656 |

The 143,520 saved predictions have zero seen-item violations and zero duplicate
recommendations. All known users received 20 results; four users had no positive
pre-test history and used popularity fallback behavior. The evaluator guard is
now active and refuses a second controlled run.

## Day 13 — Failure and stability analysis

Post-test diagnostics were run against the saved frozen output without rerunning
the evaluator or reopening model selection. There are 5,573 metric-eligible
users without a top-10 hit and 5,012 without a top-20 hit. All four no-positive-
history users exactly match the frozen popularity fallback after seen-item
removal. Duplicate and seen-item counts remain zero.

Exposure is concentrated despite 0.638513 catalog coverage: 69.1088% of slots
come from the top popularity decile and the most-exposed 1% of catalog items
receive 48.8134% of slots. Three 200-resample user-level bootstrap runs (seeds
2026–2028) show small Monte Carlo mean spreads, with a maximum of 0.00084333
across reported metrics. These are sampling-uncertainty checks, not independent
retraining runs. See `docs/FAILURE_ANALYSIS.md` for the full table, intervals,
and limitations.
