# Serving architecture

## Data flow

The Python pipeline trains and evaluates models offline. It exports a catalog, current model manifest, saved per-user recommendation lists, model comparisons, a popularity fallback, evaluation metrics, and Item-CF neighbors. The Go API reads these JSON artifacts at startup and does not train models. The Next.js application calls the Go API through Next.js rewrites.

```text
Browser -> Next.js (3000) -> Go HTTP API (8080) -> in-memory serving artifacts
                                           -> PostgreSQL feedback and request logs
```

## Backend

- `internal/catalog` loads and indexes video metadata.
- `internal/recommender` serves frozen user recommendations, filters saved results by candidate IDs and available user history, provides popularity fallback, compares manifest model variants, and returns Item-CF neighbors.
- `internal/explanation` emits only reason codes carried by the serving predictions or generated from the active scoring path.
- `internal/database` stores feedback and recommendation request metadata in PostgreSQL. `:memory:` is a test-only in-memory adapter.
- `internal/telemetry` provides request IDs, structured request logs, response time, and process counters.
- `internal/httpapi` exposes recommendation, comparison, catalog, model, feedback, health, readiness, metrics, and similar-item endpoints.

PostgreSQL is the deployment database, matching the parent project plan. The schema uses PostgreSQL `TIMESTAMPTZ`; a local test adapter keeps Go unit tests independent of a database service.

## Model identity and evaluation

Model IDs and weights come from `backend/serving_data/model_manifest.json`. The selected hybrid is 0.90 Item-CF, 0.00 LightGCN, and 0.10 popularity. LightGCN is an evaluated, rejected component. The API serves the saved selected-model predictions; experimental comparison lists are loaded from their separate artifact. `metrics_summary.json` contains validation comparisons and a separate, single controlled-test result. The UI labels these separately.

Training and test histories are not present in the checked-in serving bundle. Saved predictions were exported with the offline candidate protocol, which already removes seen training/validation items. Runtime `exclude_seen` can remove more items only when a corresponding history file is supplied. Do not describe live feedback as online model learning.

## Item similarity artifact

`backend/serving_data/item_similarity.json` is exported from the checksum-verified frozen Item-CF matrix and mapping. To reproduce it from the parent project root, run:

```powershell
python backend-frontend/scripts/export_item_similarity.py
```

The companion `item_similarity_manifest.json` records source and output hashes. The video detail route reads this index through `GET /api/v1/videos/{videoId}/similar`.

## Runtime and deployment

Docker Compose starts PostgreSQL, the API, and Next.js. Copy `.env.example` to `.env` and set a private local password before starting. `/healthz` checks process liveness; `/readyz` also checks the catalog and database. The API returns a numeric `X-Response-Time-Ms` header and `X-Request-ID`.
