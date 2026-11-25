# Demonstration runbook

**Presenter:** Abdul Qadir Satti (23K-0674, BCS-7B)

## Preflight

1. Copy `.env.example` to `.env`, set a private `POSTGRES_PASSWORD`, then run `docker compose up --build` from `backend-frontend/`.
2. Verify `/healthz` and `/readyz`; open `http://localhost:3000`.
3. Use only IDs and metrics shown by the live serving manifest and evaluation data. Save screenshots and observed request IDs during the actual demo; this file is a runbook, not proof of a completed UAT.

## Flow

1. **System page:** show the current model manifest, selected weights, health/readiness, request and feedback counters. The selected hybrid is 0.90 Item-CF, 0.00 LightGCN, and 0.10 popularity. Explain that LightGCN was evaluated and rejected as a final component.
2. **Recommendations:** select a user from the API-backed list, request Top-K results, inspect ranks, source, reason evidence, and the model ID. Explain that inference serves saved offline predictions; live feedback is logged and does not update the model.
3. **Seen handling:** point out the frozen offline candidate protocol. State that additional runtime seen filtering requires a user history artifact; this serving bundle does not contain one.
4. **Cold start:** use the explicit cold-start control. Confirm the response reports `fallback: true`, the popularity fallback model ID, and the `cold_start` reason code.
5. **Model comparison:** compare the same returned demo user across the four manifest model IDs. Point out that the selected hybrid has 0 LightGCN weight.
6. **Metrics:** distinguish validation comparison rows from the one controlled test result. The selected hybrid's frozen test values in the current artifact are Recall@10 `0.012742`, NDCG@10 `0.015098`, Hit Rate@10 `0.109033`, and coverage `0.638513`; 6,255 of 7,176 users were metric-eligible.
7. **Video details and feedback:** open an ID from the live feed, show neighbors returned by the Item-CF similarity endpoint, submit feedback, and confirm the PostgreSQL-backed action counts in `/metrics`.

Avoid quoting latency targets until measured on the demo machine. The browser acceptance scenarios are pending until recorded in `user_acceptance_tests.md` with screenshots and observed outputs.
