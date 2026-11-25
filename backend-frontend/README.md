# KuaiRec recommender — Go API and Next.js demo (Abdul Qadir Satti, 23K-0674)

Serving and presentation layer of the KuaiRec explainable recommender. The Go API serves the frozen, evidence-backed artifacts produced by the offline Python pipeline in `../model` (Syed Shayan Mustufa Rizvi, 23K-0924); the Next.js app presents them; PostgreSQL stores feedback and logs. See `docs/ARCHITECTURE.md` and `docs/API_SPEC.md`.

## Tested versions

| Component | Version |
|---|---|
| Docker images | `golang:1.22.12-alpine3.21` (build), `alpine:3.21.3`, `node:20.18.1-alpine3.20`, `postgres:16.6-alpine3.20` |
| Go | module `go 1.22`; tested with go1.22.12 (Docker) and go1.27.4 (Windows) |
| Node / npm | Node 20.18.1 (Docker), Node 24.15.0 + npm 11.12.1 (local); exact package versions pinned in `frontend/package.json` + lockfile |
| Docker | Docker Desktop 29.8.2, Compose v2 |

## Run with Docker (primary)

```powershell
cd backend-frontend
copy .env.example .env        # then set POSTGRES_PASSWORD (and API_PORT/WEB_PORT if 8080/3000 are taken)
docker compose up --build -d
docker compose ps             # all three services "healthy"
```

Open `http://localhost:3000` (or `WEB_PORT`). API: `http://localhost:8080/readyz`. Stop with `docker compose down` (data kept) or `docker compose down -v` (also deletes feedback/logs).

## Backup run without Docker

Needs PostgreSQL 16 and the versions above.

```powershell
# API
cd backend-frontend/backend
$env:DATABASE_URL = "postgres://kuairec:<password>@localhost:5432/kuairec?sslmode=disable"
$env:DATA_DIR = "./serving_data"
go run ./cmd/api
# Web (second terminal)
cd backend-frontend/frontend
npm ci
$env:API_INTERNAL_URL = "http://127.0.0.1:8080"
npm run build; npm start        # or: npm run dev
```

If PostgreSQL is unavailable on the demo machine, show the fallback screenshots in `docs/evidence/screenshots/` (see `docs/demo_script.md`, "Fallback plans").

## Verify

```powershell
cd backend-frontend/backend
gofmt -l . ; go vet ./... ; go test ./...                 # unit + HTTP integration tests (PostgreSQL test needs TEST_DATABASE_URL)
cd ../frontend
npm ci ; npm run lint ; npm run typecheck ; npm test ; npm run build
npx playwright install chromium
$env:E2E_BASE_URL = "http://localhost:3000" ; npm run test:e2e   # against the running stack; writes docs/evidence/screenshots
cd .. ; sh scripts/verify_restart.sh                             # feedback/logs survive API and full-stack restarts
```

## Contents

- `backend/` — Go API (chi), serving bundle `serving_data/`, synthetic test fixture `testdata/` (`make_fixture.py`).
- `frontend/` — Next.js 14 App Router + TypeScript + Tailwind; Vitest component tests in `src/__tests__`, Playwright UAT in `e2e/`.
- `scripts/` — serving-bundle generation, Item-CF neighbour export, restart verification.
- `docs/` — API spec, architecture, wireframes, project board, UAT results, demo script, slides outline, WBS gap log and completion record, `evidence/`.
