# Abdul Qadir Satti (23K-0674) — WBS gap log

**Source of truth:** `DOC-20261105-WA0002.pdf` (15-day WBS), sections 2, 6, 7, 8, 10 (Days 1–15, Abdul's bullets), 12, 13, 15.
**Audited:** `backend-frontend/` as received (baseline commit `f555c7b` on branch `worktree-abdul-wbs-completion`).
**Audit date:** 2026-11-25. **Method:** read every source/doc file; ran `go vet`, `go test ./...`, `gofmt -l`, `npm ci`, `npm run build`, `npm run lint`; compared the serving bundle with Syed's frozen artifacts in `model/artifacts/`.

Status key: **Done** = implemented and evidenced · **Partial** = present but incomplete or unverified · **Wrong** = present but incorrect / makes unsupported claims · **Missing** = not present.

## Headline findings (before fixes)

1. **Go test suite did not pass.** `go test ./...` → 10 of 12 tests FAIL: `backend/testdata/` lacks `recommendations.json` and `popularity.json`, so `recommender.NewEngine` cannot initialise. The earlier audit ("regression tests added, unrun") never executed them.
2. **Explanations were not backed by model evidence (WBS §6, §13).** Every served hybrid recommendation carried one generic `popular_in_training` reason, although the hybrid is 90 % Item-CF. Syed's evidence rule (`model/src/freeze_day9.py::build_reasons`, `model/reason_codes.json`) was ignored. All comparison rows had `reasons: []`.
3. **Fabricated scoring paths.** `scoreLightGCN` was a category/view-count heuristic labelled "lightgcn" (no embeddings used); `scorePopularity` used `log10(views) × watch_ratio_avg` where `watch_ratio_avg` is 0 for every item; `LikedBySimilarUsers` emitted a hard-coded `overlap_degree: 0.65`; the cold-start reason text claimed "curated top-performing" videos. Hybrid weights were hard-coded instead of read from the manifest.
4. **Home-page model buttons mutated global server state** (`POST /api/v1/models/switch`), so one browser changed the model for every user.
5. **Unknown vs cold-start vs known users were indistinguishable.** No user-profile artifact was served, so every non-exported ID (typo, unknown user) silently got the cold-start response; `exclude_seen` had no effect.
6. **Missing Day 8/9/10/11 items:** rate limiting, sorting/refresh controls, hybrid explanation panel, timeout / backend-unavailable UI states, unknown-user and no-history UI states, queryable logs, frontend unit/component tests, Playwright smoke test, ESLint config.
7. **Unsupported UI claims:** hero says "Go Chi / Fast API backend" and "LightGCN graph embeddings" (neither used); video page states the target is "watch ratio ≥ 1.0" (actual: `watch_ratio > 2.0`), shows `Invalid Date`, `0 seconds`, empty author, `0%` watch ratio, and asserts "strong intra-category co-occurrence"; positive training-event counts are labelled "views"; `/system` shows a fabricated "< 1.5 ms" latency when no data.
8. **Runtime acceptance never observed:** no Docker build/start, no restart persistence test, no browser UAT, no screenshots.
9. **Docker deployment could not have worked (found while fixing).** `next.config.js` built the `/api/:path*` rewrite destination as the bare `API_INTERNAL_URL` origin, so with Compose's `API_INTERNAL_URL=http://backend:8080` every API call would be proxied to `/`; Next.js also compiles rewrites at build time, but the URL was only supplied at runtime.
10. **Checksum/line-ending hazard (found while fixing).** The Python export scripts wrote JSON with Windows CRLF while git stored LF, so any checksum recorded for those files would not match a fresh checkout.

## Item-by-item (Abdul's WBS bullets)

| Day | WBS item (Abdul) | Status found | Evidence / gap |
|---|---|---|---|
| 1 | Next.js + Go repository structure | Done | `backend/cmd/api`, `internal/{catalog,config,recommender,explanation,telemetry,httpapi,database}`, `frontend/src/{app,components,lib,types}` match WBS §3. |
| 1 | Linting, formatting | **Missing** | `npm run lint` has no ESLint config/dependency (interactive prompt); no Prettier; 10/10 Go files fail `gofmt -l`. |
| 1 | Docker, environment files | Partial | Dockerfiles/compose/.env.example exist; backend Dockerfile copies `go.mod` only and there is no `go.sum` (`go mod download` cannot verify modules); never built. |
| 1 | API contract + frontend wireframes | Partial | `docs/API_SPEC.md` exists; **no wireframes**. |
| 1 | Project board columns (Backed Up, Planned, In Progress, Review, Blocked, Done) | **Missing** | No board artifact. |
| 1 | Reproducibility README | Partial | README exists but no pinned Node/npm/Go versions (WBS §2.1 requires exact pins); `package.json` uses `^` ranges. |
| 2 | Typed Go domain types; request/response structs | Done | `recommender.RecommendationRequest/Response`, `RecommendedItem`. |
| 2 | Placeholder health + recommendation endpoints | Done | `/healthz`, `/api/v1/recommendations`. |
| 2 | Frontend user selector + empty shell | Done | `app/page.tsx`. |
| 2 | Compose services for API + frontend | Partial | Present (plus PostgreSQL); not run. |
| 3 | Go artifact reader | Done | Loads manifest, catalog, recommendations, popularity, similarity. |
| 3 | Model manifest format | Partial | Format exists but hybrid weights are hard-coded in Go rather than read from it; manifest omits artifact checksums. |
| 3 | Validation for unknown users and unseen items | **Wrong** | Unknown users silently treated as cold start; unknown `candidate_ids` silently dropped; `top_k` out of range silently clamped. |
| 3 | Cold-start fallback endpoint behaviour | Partial | Works, but reason text/evidence invented ("curated", no `fallback_model_id`/count as required by `reason_codes.json`). |
| 3 | Frontend loading, empty, error states | Done | Present on all routes. |
| 4 | Connect backend to popularity artifact | Partial | `popularity.json` is used for cold start only; the "popularity" model path ignored it and scored `log10(views)×0`. |
| 4 | Ordered recommendations with cold-start fallback | Done | Ranks assigned; fallback flag returned. |
| 4 | Recommendation cards, loading skeleton, rank labels | Done | `VideoCard`, `SkeletonCard`. |
| 4 | Server-side request validation | Partial | `user_id` required; no `top_k` range error, no candidate validation, no body size limit, unknown JSON fields accepted. |
| 5 | Source and score fields | Done | Present on every item. |
| 5 | Model comparison state in frontend | Partial | `/compare` exists; home model toggle mutates global state (finding 4). |
| 5 | Error handling for unknown IDs | **Wrong** | See Day 3. |
| 5 | API integration tests | **Wrong** | Tests exist but 10/12 fail (finding 1). |
| 5 | Show API response latency | Done | `latency_ms` and `X-Response-Time-Ms`. |
| 6 | Comparison route | Done | `/compare`. |
| 6 | Video metadata cards and placeholders | **Wrong** | Shows fabricated/blank fields and wrong target definition (finding 7). |
| 6 | Recommendation evidence panel | Partial | Evidence badges exist but the served evidence was generic (finding 2). |
| 6 | Explanation data structure and presentation | Partial | Structure matches WBS §6; content unsupported. |
| 7 | Manifest switching in Go | Partial | Works only as global mutable state; no per-request model selection. |
| 7 | Deterministic explanation builders | **Wrong** | Builders emit constants not derived from inputs (finding 3). |
| 7 | Source attribution in UI | Done | `Source:` label on cards. |
| 7 | API cache / preload "if needed" | Done | Artifacts preloaded at startup. |
| 8 | Weighted hybrid artifact consumption | Partial | Hybrid served from saved predictions; component scores dropped; weights hard-coded. |
| 8 | Model comparison API data | Partial | `/api/v1/compare` returns lists without reasons. |
| 8 | Hybrid explanation panel | **Missing** | No per-item α·CF + β·LightGCN + γ·popularity breakdown. |
| 8 | Frontend sorting and refresh controls | **Missing** | Neither exists. |
| 9 | Complete cards, compare, metrics, system pages | Partial | Pages exist; `/system` lacks API readiness status and reproducibility details (WBS §8). |
| 9 | Pagination or top-K controls | Done | Top-K 5/10/15/20. |
| 9 | No-history and unknown-user states | **Missing** | Only a generic fallback flag. |
| 9 | Keyboard / accessibility basics | Partial | Labels not associated with controls; toggle buttons lack `aria-pressed`; no skip link; never verified. |
| 9 | Loading, timeout, backend-unavailable states | Partial | Loading yes; **no request timeout and no distinct backend-unavailable state**. |
| 10 | PostgreSQL schema | Done | `feedback_events`, `recommendation_logs` (`TIMESTAMPTZ`). |
| 10 | Store API requests, feedback, recommendation metadata | Partial | No API request log table; recommendation log stores an empty `request_id` (header read before the ID middleware runs). |
| 10 | Structured logs | Partial | JSON `slog`, but `request_id` is empty in every log line (middleware order bug); no status code logged. |
| 10 | Request ID + latency middleware | Partial | Present; ID not propagated to logs/DB. |
| 10 | `/healthz`, `/readyz`, `/metrics` | Done | Present. |
| 10 | CORS **and rate limiting** | Partial | CORS present; **rate limiting missing**. |
| 10 | Exit: feedback survives restart, logs queryable | **Missing evidence** | Never run; no endpoint or documented query for logs. |
| 11 | Run API integration tests | **Wrong** | Fail (finding 1). |
| 11 | Frontend unit/component tests | **Missing** | None. |
| 11 | Verify Docker build | **Missing evidence** | Never built. |
| 11 | Playwright smoke test | **Missing** | None. |
| 11 | Mobile responsiveness / console errors | **Missing evidence** | Never checked. |
| 12 | Finalize compose, serve frontend + API | Partial | Config present; never started. |
| 12 | Reverse proxy / CORS / env vars | Partial | Next.js rewrites; `/metrics` rewrite path broken when `API_INTERNAL_URL` lacks `/api`; `.env.example` lists unused `NEXT_PUBLIC_API_URL`. |
| 12 | Clean machine restart test | **Missing evidence** | Not performed. |
| 12 | Deployment instructions | Partial | README only. |
| 13 | ≥5 end-user test scenarios | **Missing evidence** | UAT plan only, all pending. |
| 13 | Route transitions and mobile behaviour | **Missing evidence** | — |
| 13 | Fix display issues, timeouts, empty states, inaccessible controls | Partial | See Day 9. |
| 13 | Screenshots and demo evidence | **Missing** | None. |
| 14 | Record demo flow and screenshots | **Missing** | None. |
| 14 | Presentation slides | Partial | Markdown outline only; no deck. |
| 14 | Document architecture and API | Partial | Docs exist; describe the fabricated paths as real. |
| 14 | Explanation for each demo screen | Partial | Demo runbook exists; not per screen. |
| 15 | Final deployment smoke test | **Missing evidence** | — |
| 15 | Freeze Docker images / compose config | Partial | Base images by tag only; no digest/version record. |
| 15 | Backup run instructions + fallback screenshots | **Missing** | — |
| 15 | Second-machine startup | **Missing evidence** | — |
| 15 | Demo talking points + fallback plans | Partial | Runbook has no fallback plan. |

Resolution of each item is recorded in [ABDUL_WBS_COMPLETION.md](./ABDUL_WBS_COMPLETION.md).
