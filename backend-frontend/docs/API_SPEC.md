# Go API contract

Base URL: `http://localhost:8080`. Browser requests in the Next.js app are proxied by rewrites. JSON uses UTF-8. Model IDs are read from `backend/serving_data/model_manifest.json`:

- `popularity-positive-event-count-v1`
- `item-cf-cosine-v1`
- `lightgcn-validation-selected-v1`
- `hybrid-validation-selected-v1`

## Recommendations

`POST /api/v1/recommendations`

```json
{"user_id":"0","top_k":10,"exclude_seen":true,"candidate_ids":[]}
```

`user_id` is required. `top_k` defaults to 10 and is capped at 50. `candidate_ids` is optional. The response contains `user_id`, `model`, `top_k`, `recommendations`, `fallback`, `generated_at`, and `latency_ms`. Each recommendation contains `item_id`, `rank`, `score`, `source`, optional `video`, and `reasons`.

Unknown users receive the popularity fallback. Saved per-user predictions are served from the frozen offline export. The export uses the offline seen-item protocol; the API can additionally remove history items only when a history artifact is configured.

## Catalog and similar items

- `GET /api/v1/videos/{videoId}` returns catalog metadata or `404`.
- `GET /api/v1/videos/{videoId}/similar?top_k=5` returns Item-CF neighbors ordered by cosine similarity. `top_k` must be from 1 to 20.

The similar endpoint returns `{ "item_id": "...", "similar_items": [{ "item_id": "...", "score": 0.42, "video": {} }] }`.

## Models and comparison

- `GET /api/v1/models` lists model metadata and current model ID.
- `GET /api/v1/models/current` returns the complete manifest.
- `POST /api/v1/models/switch` accepts `{ "model_id": "item-cf-cosine-v1" }`; an unknown ID returns `400`.
- `GET /api/v1/compare?user_id=0&top_k=5` returns saved results for each model without changing the process-wide active model. `user_id` is required; `top_k` must be 1 through 50.
- `GET /api/v1/users` returns a bounded list of demo user IDs and history availability.

## Feedback and operations

- `POST /api/v1/feedback` accepts `user_id`, `item_id`, `action`, and optional `model_id`. Actions are `click`, `play`, `skip`, and `hide`. Events are persisted in PostgreSQL.
- `GET /api/v1/metrics/offline` returns the checked-in evaluation summary. Validation comparisons and the selected model's controlled-test metrics are separate fields.
- `GET /healthz` is the liveness endpoint.
- `GET /readyz` checks database connectivity and catalog availability.
- `GET /metrics` returns process request, latency, error, recommendation, and feedback counters.

Successful responses include `X-Request-ID` and numeric `X-Response-Time-Ms` headers. CORS origins are configured through `ALLOWED_ORIGINS`.
