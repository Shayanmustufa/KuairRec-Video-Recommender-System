# Model Card — KuaiRec Hybrid Recommender

## Status

Final after the single controlled test pass. Model selection was completed using
validation data only and remained locked after test results were viewed. This
card describes offline evidence, not production readiness.

## Model identity

- **Model ID:** `hybrid-validation-selected-v1`
- **Task:** offline top-K short-video recommendation for known KuaiRec users
- **Selected components:** 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN
- **Primary validation objective:** NDCG@10, with Recall@10 secondary
- **Candidate protocol:** full eligible catalog minus the user's seen history
- **Frozen evidence:** `model/artifacts/test_time_manifest.json`

## Training data and target

The model uses KuaiRec 2.0 Big Matrix interactions. The derived relevance proxy
is `watch_ratio > 2.0`; it is not an explicit like label. Data is deduplicated
on `(user_id, video_id, timestamp)`, split chronologically per user, and filtered
through a distinct-edge training-only 5-core. Validation and test interactions
do not define training eligibility or model features.

Popularity counts positive training events. Item-CF uses binary-positive cosine
similarity with shrinkage and a maximum `log1p(watch_ratio)` preference strength
per positive training user–item pair. LightGCN was trained and evaluated but
received zero hybrid weight because it underperformed both baselines.

## Validation results

Metrics average over 6,761 users with at least one eligible relevant validation
candidate; 415 users without one are reported separately. The complete grid and
ablations are in `docs/EXPERIMENTS.md`.

| Metric | Hybrid |
|---|---:|
| Recall@10 | 0.014071 |
| Recall@20 | 0.029101 |
| NDCG@10 | 0.016448 |
| NDCG@20 | 0.021916 |
| Precision@10 | 0.013829 |
| Precision@20 | 0.014931 |
| Hit Rate@10 | 0.113888 |
| Hit Rate@20 | 0.208697 |
| Catalog coverage@20 | 0.622832 |

The hybrid improves every reported ranking metric over Item-CF. It improves
most secondary metrics and coverage over popularity, but popularity remains
slightly better on Recall@10 and NDCG@10. The hybrid is not claimed to dominate
all baselines universally.

## Ablation decision

The validation grid evaluated all 66 nonnegative 0.1-step weight triples and
recorded single-component and best pairwise ablations. The selected hybrid is
identical to the best configuration without LightGCN, so LightGCN contributes
no score or explanation to the final model. Removing popularity reduces the
selected configuration to Item-CF and lowers every reported full-validation
ranking metric. These are validation findings only; the controlled test was not
used to revisit this decision.

## Controlled test results

The frozen model was evaluated once. Metrics average over 6,255 users with an
eligible relevant test candidate; 921 users without one are reported through
evaluation coverage.

| Metric | Test |
|---|---:|
| Recall@10 | 0.012742 |
| Recall@20 | 0.025472 |
| NDCG@10 | 0.015098 |
| NDCG@20 | 0.019188 |
| Precision@10 | 0.012902 |
| Precision@20 | 0.013397 |
| Hit Rate@10 | 0.109033 |
| Hit Rate@20 | 0.198721 |
| Catalog coverage@20 | 0.638513 |

All 143,520 recommendations passed duplicate and seen-item checks. These results
did not trigger any model, weight, or hyperparameter change.

## Explanations

Every frozen validation recommendation has machine-readable evidence validated
against actual model inputs:

- `liked_by_similar_users` records the strongest positive-history Item-CF
  contributor, similarity, preference strength, contribution, and component
  weight.
- `popular_in_training` records the raw positive training-event count and
  popularity weight.
- `cold_start` is reserved for unknown users or users without eligible positive
  history and uses the frozen popularity fallback.
- `extension_model_match` is disabled because LightGCN weight is zero.
- `similar_to_recent` is disabled because the strongest similarity contributor
  is not necessarily the most recent item.

The validation report covers 143,520 recommendations with 100% supported-reason
coverage and no unsupported LightGCN claims.

## Intended use

The system is intended for an educational, offline demonstration of
reproducible recommendation, evaluation, cold-start fallback, and
evidence-backed explanations. It can rank known eligible catalog items for
known users and provide popularity recommendations for unknown/cold-start users.

## Out-of-scope use

Do not use this model for production personalization, safety-critical decisions,
profiling sensitive characteristics, or claims about friendship/taste. Feedback
is not online learning. The model should not recommend items outside the frozen
eligible catalog without a separately validated policy.

## Limitations and risks

- `watch_ratio > 2.0` is a derived engagement proxy and can favor repeated or
  unusually long playback rather than satisfaction.
- Offline ranking metrics are low and do not establish user benefit.
- Popularity can reinforce exposure bias; Item-CF can over-specialize around
  observed history.
- KuaiRec users, collection conditions, and time period may not represent other
  populations or current behavior.
- Users/items excluded by the eligibility filter require a fallback and are not
  represented by warm-user metrics.
- Category, creator, demographic, and content-safety fairness are not evaluated.
- Controlled test performance remains low in absolute terms and does not
  establish user satisfaction or production readiness.
- 89.10% of metric-eligible users have no relevant result in the top 10, and
  80.13% have none in the top 20 under the derived relevance proxy.
- Exposure is concentrated: 69.11% of recommendation slots come from the top
  popularity decile and the most-exposed 1% of items receive 48.81% of slots,
  despite catalog coverage@20 of 63.85%.
- Seeded bootstrap checks quantify test-user sampling uncertainty only; they do
  not establish stability across independent retraining runs.

## Reproducibility and governance

The release, split, configurations, selected weights, artifacts, reason rules,
and SHA-256 checksums are recorded in generated manifests. `model/reason_codes.json`
is the serving explanation contract. Any change to a frozen artifact invalidates
the Day 9 freeze and requires a new manifest before test evaluation. Raw data,
generated predictions, and model artifacts remain outside source control.

The canonical serving identity is `model/artifacts/model_manifest.json`.
`model/artifacts/system_metadata.json` is a UI-ready projection containing the
dataset release, selected model, controlled-test summary, and explanation
contract. The metadata contract is verified in this repository; actual UI
rendering cannot be verified until Abdul's frontend implementation is present.
`model/artifacts/claim_audit.json` records the evidence checks and this pending
integration boundary.
