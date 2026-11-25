# Go API specification

Base URL: `http://localhost:${API_PORT:-8080}`. The Next.js app proxies `/api/*`, `/healthz`, `/readyz` and `/metrics-api` (→ `/metrics`) to the API, so browsers use same-origin relative URLs. All bodies are UTF-8 JSON. Unknown JSON fields are rejected. Every response carries `X-Request-ID` (echoed if the client sends a valid one, else generated) and `X-Response-Time-Ms` (server time until headers were written). Errors are `{"error": "<message>"}`.

`/api/v1/*` is rate limited per client IP (`RATE_LIMIT_PER_MINUTE`, default 300) → `429`. CORS allows only `ALLOWED_ORIGINS`.

Model IDs (from `serving_data/model_manifest.json`):

| ID | Role |
|---|---|
| `hybrid-validation-selected-v1` | Selected model: 0.9 Item-CF + 0.0 LightGCN + 0.1 popularity |
| `popularity-positive-event-count-v1` | Baseline and cold-start fallback |
| `item-cf-cosine-v1` | Baseline |
| `lightgcn-validation-selected-v1` | Evaluated, rejected extension (zero hybrid weight) |

## POST /api/v1/recommendations

```json
{ "user_id": "0", "top_k": 10, "exclude_seen": true, "candidate_ids": null,
  "model": "hybrid-validation-selected-v1", "force_cold_start": false }
```

| Field | Rule |
|---|---|
| `user_id` | required, `[A-Za-z0-9_.-]{1,64}` |
| `top_k` | 1–20 (frozen lists hold 20 items); omitted/0 → 10; otherwise `400` |
| `exclude_seen` | default `true`; removes the user's pre-test seen items where the history is exported (demo users); saved lists already exclude seen items by protocol |
| `candidate_ids` | optional filter; any ID outside the eligible catalog → `400` listing up to 10 unknown IDs |
| `model` | optional, **this request only** (never changes shared state); unknown → `400`; non-selected models serve validation-time lists exported for demo users, otherwise `404` |
| `force_cold_start` | optional; serve the fallback a new user would get |

User handling:

| Situation | `user_status` | `fallback` | `fallback_reason` | Model served |
|---|---|---|---|---|
| Known user with positive history | `known` | `false` | — | requested/default model |
| Known user, no positive history | `no_positive_history` | `true` | `no_positive_history` | popularity fallback |
| ID not in training data | `unknown` | `true` | `unknown_user` | popularity fallback |
| `force_cold_start: true` | as above | `true` | `cold_start_requested` | popularity fallback |

Response (WBS §7 fields plus provenance):

```json
{
  "user_id": "0", "model": "hybrid-validation-selected-v1", "top_k": 10,
  "fallback": false, "user_status": "known", "artifact_split": "test", "exclude_seen": true,
  "generated_at": "2026-11-25T07:37:09Z", "latency_ms": 0.021,
  "recommendations": [{
    "item_id": "10434", "rank": 1, "score": 0.921318114, "source": "hybrid-validation-selected-v1",
    "video": { "item_id": "10434", "title": "…", "category": "二次元", "categories": ["…"], "tags": [],
               "author_id": "1503", "upload_date": "2020-08-26", "video_type": "NORMAL",
               "duration_seconds": 11.7, "has_caption": true, "positive_training_events": 4 },
    "components": {
      "item_cf":   { "normalized_score": 1.0,   "weight": 0.9, "contribution": 0.9 },
      "lightgcn":  { "normalized_score": 0.364, "weight": 0.0, "contribution": 0.0 },
      "popularity":{ "normalized_score": 0.213, "weight": 0.1, "contribution": 0.0213 }
    },
    "reasons": [
      { "code": "liked_by_similar_users", "text": "Recommended from collaborative patterns linked to your positive history.",
        "evidence": { "source_video_id": "3289", "similarity": 0.0044, "preference_strength": 4.50,
                      "contribution": 0.0199, "item_cf_weight": 0.9 } },
      { "code": "popular_in_training", "text": "Popular in positive training interactions.",
        "evidence": { "positive_training_event_count": 4, "popularity_weight": 0.1 } }
    ]
  }]
}
```

`artifact_split`: `test` = frozen controlled-test ranking from train+validation history; `validation` = validation-time list from training history; `train` = training-only popularity fallback. Each successful call is stored in `recommendation_logs` with the request ID and returned item IDs.

### Explanations

Reason codes and required evidence come from `model/reason_codes.json` (frozen in the manifest). The API refuses to start if any served reason lacks a required evidence key or if the selected model's lists use a disabled code.

| Code | Enabled | Required evidence |
|---|---|---|
| `liked_by_similar_users` | yes | `source_video_id`, `similarity`, `preference_strength`, `contribution`, `item_cf_weight` |
| `popular_in_training` | yes | `positive_training_event_count`, `popularity_weight` |
| `cold_start` | yes | `fallback_model_id`, `positive_training_event_count` (+ `user_status`, `forced`) |
| `extension_model_match` | no (β = 0) | `lightgcn_score`, `lightgcn_weight` — only in the rejected LightGCN comparison lists |
| `similar_to_recent` | no | not emitted: the strongest Item-CF contributor is not necessarily the most recent item |

## GET /api/v1/compare?user_id=&top_k=

Validation-time lists of all four models for the same user and candidate protocol (full eligible catalog minus training-seen items). `top_k` 1–20, default 5. Users without an export → `404` (use `GET /api/v1/users`). Columns with no supported signal are empty with `empty_reason`.

## Users, catalog, similarity

- `GET /api/v1/users` — the 100 demo users (stratified by history size, including the 4 users without positive history): `user_id`, `status`, `positive_history_items`, `seen_items`.
- `GET /api/v1/users/{userID}` — known user's counts and up to 5 recent positive videos (demo users); unknown → `404 {"user_status":"unknown"}`.
- `GET /api/v1/videos/{videoID}` — official catalog metadata or `404`.
- `GET /api/v1/videos/{videoID}/similar?top_k=5` — frozen Item-CF cosine neighbours (1–20).

## Models

- `GET /api/v1/models` — model list, selected, fallback and server-default model.
- `GET /api/v1/models/current` — full manifest incl. weights, reason rules, serving provenance, source/bundle SHA-256, `bundle_verified_at_load`.
- `POST /api/v1/models/switch` `{"model_id": "…"}` — admin: changes the server default for requests that name no model. Requires `X-Admin-Token` when `ADMIN_TOKEN` is set. The UI does not use it.

## Feedback and logs

- `POST /api/v1/feedback` `{"user_id","item_id","action","model_id"?, "rank"?}` → `201`. `action` ∈ click/play/skip/hide; `item_id` must be in the catalog; `model_id` must be registered (default: server default); `rank` 1–20. Stored in PostgreSQL with the request ID. Feedback does **not** retrain any model.
- `GET /api/v1/feedback?user_id=&limit=` — newest events + per-action totals.
- `GET /api/v1/logs/requests?request_id=&limit=` — persisted API request log (method, path, status, duration).
- `GET /api/v1/logs/recommendations?user_id=&request_id=&limit=` — served list metadata.
- `GET /api/v1/metrics/offline` — validation comparison, split summary and the single controlled-test result.

## Operations

- `GET /healthz` — liveness (no dependencies).
- `GET /readyz` — `200` only if PostgreSQL answers and the catalog/recommendations are loaded; else `503` with per-check status.
- `GET /metrics` — process counters: requests, 2xx/4xx/5xx, rate-limited, recommendations, fallbacks, feedback, mean latency, uptime, persisted feedback by action.

## PostgreSQL schema

`feedback_events(id, request_id, user_id, item_id, action CHECK IN (click,play,skip,hide), model_id, rank, created_at TIMESTAMPTZ)`, `recommendation_logs(id, request_id, user_id, user_status, model_id, top_k, is_fallback, item_ids JSONB, latency_ms, recommended_at)`, `api_requests(id, request_id, method, path, status, duration_ms, remote_addr, created_at)`. The DDL in `internal/database/db.go` is idempotent and applied at start-up.
