# KuaiRec recommender presentation outline

## 1. Goal and ownership

- Explainable short-video recommendations built from the KuaiRec 2.0 Big Matrix.
- Abdul Qadir Satti: Go API, Next.js demo, PostgreSQL persistence, integration, and delivery.
- Syed Shayan Mustufa Rizvi: data preparation, model experiments, evaluation, and scientific reporting.

## 2. System architecture

- Python trains/evaluates offline and exports serving artifacts.
- Go loads the catalog, manifest, saved user recommendations, comparisons, fallback list, and Item-CF neighbors.
- Next.js presents recommendation, video, compare, metrics, and system routes.
- PostgreSQL stores feedback and recommendation request metadata.

## 3. Model results

- Target: derived positive event `watch_ratio > 2.0`; this is not an explicit satisfaction label.
- Selected validation hybrid: 0.90 Item-CF + 0.00 LightGCN + 0.10 popularity.
- LightGCN was evaluated but rejected as a standalone model and receives zero weight in the selected hybrid.
- The controlled test result is reported separately from validation; only the selected hybrid had a controlled test pass.

| Selected hybrid controlled-test metric | Value |
|---|---:|
| Recall@10 | 0.012742 |
| NDCG@10 | 0.015098 |
| Hit Rate@10 | 0.109033 |
| Precision@10 | 0.012902 |
| Catalog coverage | 0.638513 |

The metric-eligible population was 6,255 of 7,176 users. See the parent project report for protocol details and limitations.

## 4. API and explainability

- Recommendation, model, comparison, catalog, similar-item, feedback, liveness/readiness, and metrics endpoints.
- Manifest model IDs and saved reason codes are visible to the UI.
- The video detail page uses frozen Item-CF cosine neighbors.
- Feedback is persisted for analysis; it is not online learning.

## 5. User experience

- Recommendation feed with real API-backed user list, Top-K controls, model selection, loading and error states.
- Cold-start fallback control, model comparison, offline metrics, video details, similar items, and feedback controls.
- Demonstrate keyboard and narrow viewport behavior only after the pending UAT rows have been tested.

## 6. Deployment and evidence

- Docker Compose runs PostgreSQL, Go API, and Next.js.
- `/healthz`, `/readyz`, `/metrics`, request IDs, structured logs, and response-time header.
- `docs/ABDUL_WORK_AUDIT.md` and `docs/user_acceptance_tests.md` distinguish code review/build evidence from runtime checks still pending.
