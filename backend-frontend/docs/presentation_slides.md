# Presentation outline (content source for the slide deck)

The deck built from this outline: https://claude.ai/artifact/AeM7mkyrUvmJfw6Dd51VEo (Claude Slides; private until the owner shares it; Share › Export gives PPTX or PDF).

All numbers come from `backend/serving_data/metrics_summary.json` and match the `/metrics` page. Screenshot file names refer to `docs/evidence/screenshots/`.

## 1. Title
KuaiRec Explainable Short-Video Recommender — Abdul Qadir Satti (23K-0674, BCS-7B), Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A).

## 2. Problem and goal
Explainable recommendations on KuaiRec 2.0 with a leakage-safe evaluation and an end-to-end demo. Relevance proxy: `watch_ratio > 2.0` (not an explicit like label).

## 3. Architecture
Python offline pipeline → frozen, checksummed artifacts → Go API (chi) → Next.js; PostgreSQL for feedback and logs. Diagram: `ARCHITECTURE.md`. Screenshot: `desktop-uat08-system.png`.

## 4. Data and protocol
7,176 users, 8,418 eligible items; per-user chronological 70/15/15; full-catalog candidates minus seen items; seed 2026.

## 5. Models
Popularity, Item-CF (cosine), LightGCN (evaluated, rejected), validation-tuned hybrid 0.9 Item-CF + 0.1 popularity + 0 LightGCN.

## 6. Results (validation, model selection)

| Model | Recall@10 | NDCG@10 | Hit@10 | Coverage@20 |
|---|---:|---:|---:|---:|
| Popularity | 0.0157 | 0.0168 | 0.0992 | 2.6% |
| Item-CF | 0.0122 | 0.0154 | 0.1089 | 66.2% |
| LightGCN (rejected) | 0.0086 | 0.0093 | 0.0658 | 57.1% |
| Hybrid (selected) | 0.0141 | 0.0164 | 0.1139 | 62.3% |

Honest result: the hybrid matches popularity on NDCG@10 while covering ~24× more of the catalogue and achieving the highest Hit@10.

## 7. Controlled test (selected hybrid, single pass)
Recall@10 0.0127 · NDCG@10 0.0151 · Hit@10 0.1090 · Precision@10 0.0129 · Recall@20 0.0255 · coverage 63.9%; 6,255 of 7,176 users metric-eligible.

## 8. Explainability
Each result shows machine-readable evidence: source video, similarity, preference strength, contribution, weights; popularity counts; cold-start reason. Evidence validated at API start-up. Screenshot: `desktop-uat01-known-user.png`.

## 9. Demo states
Known user, unknown user, no positive history, requested cold start, timeout, backend unavailable. Screenshots: `desktop-uat02…`, `uat03…`, `uat04…`, `uat09…`.

## 10. Engineering quality
Go: 27 tests + 11 subtests, PostgreSQL integration test. Frontend: 20 component tests, 21 Playwright scenarios on desktop and mobile. Docker clean-clone deploy; feedback survives restarts; rate limiting, CORS, request-ID logs.

## 11. Limitations and future work
Proxy relevance label; popularity dominance in accuracy metrics; comparison lists for 100 demo users; no online learning; social links not used as taste evidence; future: sequential model, online feedback loop.
