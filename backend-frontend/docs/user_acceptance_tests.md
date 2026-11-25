# User acceptance test plan

**Execution status: pending observed run.** The previous copy marked five scenarios PASS but named fictional users/videos, expected metrics absent from the frozen evaluation artifact, and claimed SQLite while the service uses PostgreSQL. Those outcomes were not accepted as test evidence. Use the steps below after starting the Compose stack; record date, browser, screenshots, request IDs, and observed values before marking a scenario passed.

## Start

1. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD`.
2. Run `docker compose up --build` from `backend-frontend/`.
3. Open `http://localhost:3000`; check `http://localhost:8080/healthz` and `/readyz`.

## Scenarios

| ID | Scenario | Expected check | Current status |
|---|---|---|---|
| UAT-01 | Known saved user | Choose a user returned by `/api/v1/users`; recommendations load, each item has rank/catalog metadata, and model ID matches the manifest. | Pending browser run |
| UAT-02 | Cold start | Enable the cold-start control or use an unknown ID; response has `fallback: true`, the manifest's popularity model ID, and `cold_start` reasons. | Pending browser run |
| UAT-03 | Seen/candidate filtering | Verify the offline saved list follows the recorded candidate protocol; if `user_history.json` is configured, request `exclude_seen: true` and confirm history IDs are absent. | Pending; serving bundle has no user history file |
| UAT-04 | Model switching/comparison | Switch among the exact manifest IDs; `/api/v1/compare` returns all four model keys and does not change `/api/v1/models/current`. | Pending Go/API run |
| UAT-05 | Feedback persistence | Submit each supported action, restart the API/container, and confirm PostgreSQL retains the events and `/metrics` reflects feedback counts. | Pending Compose run |
| UAT-06 | Video detail similarity | Open a valid catalog ID and confirm `/similar` returns Item-CF neighbors in descending score order; unknown IDs return 404. | Pending Go/API run |
| UAT-07 | Responsive and error states | Check narrow viewport, loading/empty/backend-down states, keyboard controls, and browser console. | Pending browser run |

## Automated checks

The Go test suite lives under `backend/`; frontend type-check and production build use `npm run build`. At the time this document was updated, the frontend build passed. Go tests and Docker startup were not run because the current environment has no Go executable; browser UAT also has no recorded run evidence. Do not mark a row PASS until its behavior is observed and evidence is saved.
