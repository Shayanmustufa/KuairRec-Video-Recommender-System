# User acceptance tests — results

**Run:** 2026-11-25 against the Docker Compose stack (PostgreSQL 16.6, Go API, Next.js standalone) built from branch `worktree-abdul-wbs-completion`.
**How:** `frontend/e2e/uat.spec.ts` (Playwright 1.49.1, Chromium 131) in two projects — desktop 1440×900 and mobile Pixel 7. Raw results: `evidence/playwright_results.tsv`, `evidence/playwright_summary.txt`. Screenshots: `evidence/screenshots/{desktop,mobile}-uat*.png`.

**Result: 21 passed, 0 failed, 1 skipped by design** (keyboard scenario runs on desktop only).

| ID | Scenario | Checks | Desktop | Mobile |
|---|---|---|---|---|
| UAT-01 | Known user top-10 | user `0` → 10 cards; “Personalised” banner; model `hybrid-validation-selected-v1`; rank label; `liked_by_similar_users` evidence; score breakdown; hybrid panel; user evidence panel; no console errors | PASS | PASS |
| UAT-02 | Unknown user | ID `brand-new-user` → “Unknown user” banner, `cold_start` reason, `fallback: yes` | PASS | PASS |
| UAT-03 | No positive history | demo user `735` → “No positive history” banner and fallback | PASS | PASS |
| UAT-04 | Controls | top-K 10→5, sort by popularity, refresh, cold-start toggle → “Cold-start view requested” | PASS | PASS |
| UAT-05 | Model switch + compare | Item-CF for this request shows `split: validation`; `/models/current` default unchanged; `/compare` shows 4 model columns | PASS | PASS |
| UAT-06 | Feedback | “Play” → “Recorded”; `GET /api/v1/feedback` returns the event with a request ID | PASS | PASS |
| UAT-07 | Video detail | `/videos/5434` official metadata, `watch_ratio > 2.0` definition, Item-CF neighbours; `/videos/999999` → not-in-catalog state | PASS | PASS |
| UAT-08 | Metrics + system | controlled-test section and split summary; readiness `ready`; “checksums verified at load: yes” | PASS | PASS |
| UAT-09 | Failure states | API connection refused → “Backend unavailable”; hung API → “did not respond in time” after 8 s | PASS | PASS |
| UAT-10 | Keyboard basics | first Tab focuses “Skip to content”; all controls have labels | PASS | skipped |
| UAT-11 | All routes | `/`, `/compare`, `/metrics`, `/system`, `/videos/5434`: heading visible, no console errors, no horizontal overflow | PASS | PASS |

## Other runtime checks

| Check | Result | Evidence |
|---|---|---|
| Feedback and logs survive API restart and `docker compose down`/`up` | PASS | `evidence/restart_verification.txt` |
| PostgreSQL integration test (write, reconnect, read) | PASS | `evidence/postgres_integration_test.txt` |
| Fresh clone → build → start → smoke (checksums verified on a Windows checkout) | PASS | `evidence/clean_checkout_deploy.txt` |
| Go: `gofmt`, `go vet`, `go test ./...` (27 tests + 11 subtests) | PASS | local run |
| Frontend: lint, typecheck, Vitest (20 tests), production build | PASS | local run |

## Known limitations

- A physically separate second machine was not available; the clean-clone deployment is the closest check performed.
- Non-selected models (Item-CF, popularity, LightGCN) are servable only for the 100 demo users with exported comparison lists.
- Recent-positive history is exported for demo users only; for others the evidence panel shows counts and each reason links its source video.
- Feedback is stored for analysis; the frozen models are not retrained online.
