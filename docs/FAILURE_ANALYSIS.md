# Day 13 Failure and Stability Analysis

## Scope

This is a post-test diagnostic of the single frozen controlled-test output. It
does not rerun the test evaluator, retrain a model, change weights, reopen model
selection, or justify a new test submission. Machine-readable results are in
`model/artifacts/day13_failure_analysis.json` and
`model/artifacts/day13_failure_table.csv`.

## Failure table

| Condition | Count | Rate | Interpretation |
|---|---:|---:|---|
| No eligible relevant test candidate | 921 users | 12.8344% of all users | Not scorable under the declared denominator policy |
| No relevant recommendation in top 10 | 5,573 users | 89.0967% of metric-eligible users | Primary-cutoff ranking miss |
| No relevant recommendation in top 20 | 5,012 users | 80.1279% of metric-eligible users | Ranking miss persists at the secondary cutoff |
| No positive pre-test history | 4 users | 0.0557% of all users | Deterministic popularity fallback |
| Duplicate recommendation | 0 rows | 0% | Structural check passed |
| Previously seen recommendation | 0 rows | 0% | Structural check passed |

The high no-hit rates agree with Hit Rate@10 of 0.109033 and Hit Rate@20 of
0.198721. They are the main observed recommendation-quality failure, not an
implementation defect.

## Cold-start behavior

All four users without positive pre-test history received exactly the frozen
popularity order after removal of their previously seen items. There were no
fallback mismatches. The offline split contains no truly unknown user, so this
does not validate the external unknown-user API path.

## Popularity dominance and catalog exposure

- 69.1088% of recommendation slots contain an item from the top popularity
  decile.
- 74.6516% of rank-one recommendations come from that decile.
- The most-exposed 1% of catalog items receive 48.8134% of all recommendation
  slots.
- Despite that concentration, 5,375 of 8,418 eligible items appear at least
  once, giving catalog coverage@20 of 63.8513%.

The hybrid therefore has broad aggregate catalog reach but strongly
concentrated exposure. Coverage alone must not be interpreted as equitable or
diverse exposure.

## Seeded stability check

Three user-level bootstrap runs used seeds 2026, 2027, and 2028 with 200
resamples per seed. This quantifies sampling uncertainty in the frozen test-user
population; it is not a claim of independent retraining stability. The largest
difference between seed-specific bootstrap means was:

| Metric | Maximum mean spread |
|---|---:|
| Recall@10 | 0.00008204 |
| Recall@20 | 0.00008921 |
| NDCG@10 | 0.00001215 |
| NDCG@20 | 0.00004682 |
| Precision@10 | 0.00002158 |
| Precision@20 | 0.00003869 |
| Hit Rate@10 | 0.00003677 |
| Hit Rate@20 | 0.00084333 |

For seed 2026, the 95% bootstrap intervals were [0.010955, 0.014455] for
Recall@10, [0.013864, 0.016364] for NDCG@10, and [0.102314, 0.116547] for Hit
Rate@10. The small between-seed Monte Carlo differences do not remove the much
larger uncertainty expressed by the intervals.

## Remaining limitations

- Relevance is the derived `watch_ratio > 2.0` proxy, not satisfaction.
- Users without an eligible relevant candidate are excluded from ranking-metric
  means and must remain separately visible.
- Popularity concentration can reinforce historical exposure bias.
- Demographic, creator, category, temporal-drift, and content-safety fairness
  are not measured by the available evaluation.
- Bootstrap seeds do not substitute for independent model-training seeds.
- Offline checks do not establish production behavior or user benefit.
