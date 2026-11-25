# Abdul's backend and frontend implementation

This folder contains the Go serving API, Next.js demo, checked-in serving artifacts, and deployment files. The Python training and evaluation pipeline and its frozen artifacts are in the parent project. The API reads the actual serving manifest and metrics from `backend/serving_data`; `backend/testdata` is synthetic test-only data.

## Run locally

1. Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` with a private local password.
2. Start the stack from this directory:

   ```powershell
   docker compose up --build
   ```

3. Open `http://localhost:3000`. The Go API is available at `http://localhost:8080/healthz`.

For local development without containers, run PostgreSQL and set `DATABASE_URL`, `DATA_DIR=./serving_data`, and `ALLOWED_ORIGINS`; then run `go run ./cmd/api` from `backend/` and `npm run dev` from `frontend/`.

## Verify

```powershell
cd backend
go test ./...
cd ../frontend
npm ci
npm run build
```

`docs/ABDUL_WORK_AUDIT.md` records the item-by-item WBS review, evidence, fixes, and checks that still need a machine with Go/Docker and a browser session.

## Contents

- `backend/` — Go HTTP API, recommendation serving, PostgreSQL persistence, telemetry, and versioned serving artifacts.
- `frontend/` — Next.js user interface.
- `docs/` — API contract, architecture, demo, UAT plan, WBS cross-check, and presentation notes.
- `docker-compose.yml` — PostgreSQL, API, and frontend services.
