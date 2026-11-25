# KuaiRec Explainable Short-Video Recommender — Project Plan

## Purpose

Build a working, explainable short-video recommender using the official KuaiRec
release. The project prioritizes a scientifically sound, leakage-safe offline
evaluation and a reproducible end-to-end demonstration over interface polish.
The supplied 15-day WBS is the source of truth for scope, ownership, deliverables,
and acceptance. See [phases.md](./phases.md) for the phase-by-phase execution plan.

## Project facts

- **Team**
  - **Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A):** data engineering, training,
    recommendation algorithms, experiment design, and scientific evaluation.
  - **Abdul Qadir Satti (23K-0674, BCS-7B):** Go backend/API, frontend/demo,
    explanations, integration, deployment, and presentation.
  - Both members review each other's work using reproducible code or observed
    evidence. Scientific correctness and reproducibility remain shared concerns.
- **Product:** an offline-trained recommendation system with a Go serving API
  and a Next.js web demo.
- **Core model progression:** data audit → popularity baseline → item-based
  collaborative filtering (item-CF) → LightGCN → validation-tuned hybrid.
- **Evaluation priority:** chronological, leakage-safe train/validation/test
  splits; one consistent relevance definition and candidate protocol for every
  model; no test-set tuning.
- **Demo scope:** known-user recommendations, cold-start and unknown-user
  handling, evidence-based explanations, model comparison, metrics, feedback,
  and reproducible deployment.
- **Implementation status:** Syed's Phase 1 (Days 1–3), Phase 2 (Days 4–5), Phase 3 (Days 6–8), and Phase 4 (Days 9–10) are complete: official
  release verification, data audit, data card, deterministic temporal splits,
  training-only eligibility core, full candidate catalog, and unit tests are
  implemented. The popularity and Item-CF baselines, validation-only tuning, and
  comparison evidence, LightGCN prototype/tuning, rejected standalone result,
  and validation-selected zero-LightGCN hybrid are recorded in
  `docs/EXPERIMENTS.md`. Evidence-backed reason rules, the draft model card, and
  frozen test-time artifact manifest, final statistics, artifact inventory,
  reproduction table, and passed leakage audit are also complete. Go/backend and frontend work remains assigned to Abdul. The
  existing `model/` layout is retained rather than renamed to the WBS example
  `training/` directory.
- **Artifact hygiene:** keep raw/processed generated datasets, credentials,
  local absolute paths, and large checkpoints out of source control unless an
  explicit release policy says otherwise. Track release identifiers,
  configuration, versions, and checksums so large artifacts remain verifiable.

## Confirmed decisions

| Topic | Decision |
|---|---|
| Schedule | Keep the WBS's relative Day 1–15 sequence. Do not assign calendar dates. |
| Advanced model | Implement LightGCN as the single core extension. If its setup or validation is not viable, stop and document the issue before proposing a sequential fallback. |
| Dataset release | KuaiRec 2.0, Zenodo record 18164998, archive size 431,964,858 bytes; published MD5 and local SHA-256 are in the release manifest. |
| Relevant interaction | `watch_ratio > 2.0`, selected before evaluation from the official README's example derived-positive rule; not a native like label. |
| Duplicate policy | Deduplicate Big Matrix rows on `(user_id, video_id, timestamp)`, keep first source row, and report conflicting payloads. |
| Eligibility | Iterative user-item 5-core based on distinct user-item edges in chronological training data only; future validation/test interactions do not define the warm catalog. |
| Evaluation candidates | Full eligible training-only catalog; exclude training-seen items for validation and training-plus-validation-seen items for test. Generate lazily. |
| Database | PostgreSQL for demo persistence and deployment. |
| Frontend | Next.js + React + TypeScript, with official catalog metadata only; use neutral placeholders when media assets are unavailable. |
| Backend | Go API; use the WBS's recommended standard-library `net/http` + `chi` approach unless implementation evidence warrants a documented change. |
| Training | Python offline data processing/training. The Go service loads exported artifacts and does not train models. |
| Explanations | Deterministic reason codes backed by actual model inputs. No LLM-generated ranking or unsupported social/taste claims. |

## Open ambiguity and decisions still gated by evidence

These are not permission to guess; the named owner must resolve and record them
at the indicated stage:

1. **License metadata conflict** — the official repository
   [LICENSE](https://github.com/chongminggao/KuaiRec/blob/main/LICENSE) says CC
   BY-SA 4.0, while Zenodo metadata says CC BY 4.0. The data card conservatively
   follows CC BY-SA 4.0 and prohibits redistribution until clarified.
2. **LightGCN feasibility** — Days 6–7: use the user-video interaction graph,
   freeze seed and hyperparameters, and assess finite scores and validation
   behavior. Social links are not presumed to encode taste. Do not implement a
   second advanced model as part of the core scope.
3. **Hybrid weights** — Day 8: normalize component scores and select weights on
   validation only; record the grid, constraints, and ablation results.

The Day 2 audit reports unique users/videos; interaction counts before and after
filtering; timestamp range; duplicate and missing-value counts; engagement
range/percentiles; category distribution; user/item overlap across train and
evaluation; candidate catalog size; and social-link count if social data is used.
It confirms the published Big/Small Matrix counts. The Small Matrix has 181,992
rows without time/date/timestamp (officially associated with blocked
user-video recommendations); it is audit-only and never merged into training.
The Big Matrix has 968,005 repeated user-item-timestamp keys, including one key
with conflicting payloads; the first source row is retained.
The initial split boundaries are chronological 70% train, 15% validation, and
15% test per deduplicated user history. Eligibility is determined from distinct
user-item edges in the training partition only. Filtering items outside the training-only 5-core can
change the final row ratios; this is recorded rather than moving later events
into training to restore nominal proportions. Users with too few training
interactions belong in the cold-start group, not a random split.

## Technical shape

1. **Offline data/model pipeline (`model/`):** verify and audit the official
   release; normalize and filter records; create chronological splits and
   candidate/history exports; train popularity, item-CF, and LightGCN models;
   tune the hybrid using validation; evaluate once on the frozen test set; export
   predictions and serving artifacts with a manifest.
2. **Go service (`backend/`):** validate requests; preload and validate artifacts;
   rank/filter candidates and remove seen videos; handle unknown/cold-start
   users; return top-K results with deterministic explanations; expose health,
   readiness, and operational endpoints; persist requests/feedback in
   PostgreSQL.
3. **Web demo (`frontend/`):** provide routes for recommendations, video detail,
   model comparison, metrics, and system/reproducibility information; show rank,
   catalog metadata, score, reason/evidence, and click/watch feedback; include
   loading, empty, error, unavailable, and cold-start states.
4. **Delivery and evidence:** Docker Compose deployment, API and frontend tests,
   model/data cards, API specification, final report, presentation, screenshots,
   demo script, and backup run instructions.

## Required model and evaluation behavior

- Popularity is both a baseline and the cold-start fallback.
- Popularity uses training-only interaction counts, exposure-aware popularity,
  or training-average watch ratio; record the selected score definition.
- Item-CF uses training interactions only; tune similarity/neighborhood choices
  on validation, and remove already-seen items when requested.
- Start item-CF with cosine similarity. Its user-item score is the weighted sum
  of similarities to positively preferred history items, normalized by the sum
  of absolute similarities; use documented shrinkage if sparsity makes
  similarities unstable.
- LightGCN is the one planned advanced extension. Train on the leakage-safe
  sparse user-video bipartite graph (two or three propagation layers as the
  initial scope), export embeddings or scores, evaluate against the same
  candidate set, and retain or reject it based on recorded validation evidence.
- The hybrid combines normalized item-CF, LightGCN, and popularity scores with
  nonnegative weights summing to one. Popularity must not dominate without
  validation support.
- If sampled candidates are required, document the negative-to-positive ratio
  and ensure every evaluation user's candidates include at least one held-out
  relevant item. Use full-catalog ranking consistently if the official protocol
  and available resources support it.
- Report Recall@10 and @20, NDCG@10 and @20, Hit Rate@10, Precision@10, catalog
  coverage, and cold-start coverage where applicable. Top-K=10 is primary; K=20
  is secondary. Report validation and final test results separately, plus
  candidate protocol, filters, seed, runtime, hardware, and multi-seed variation
  if available.
- Compare popularity, item-CF, LightGCN, and hybrid; include the specified
  CF/hybrid comparisons and hybrid ablations. Never tune or select weights on
  test results.

## Explainability and API contract

Each recommendation should include item ID, rank, score, source/model, and one or
more reason objects containing a reason code, display text, and machine-readable
evidence. Allowed codes from the WBS are:

- `similar_to_recent` — above-threshold item similarity to an item in the user's
  history.
- `popular_in_training` — training-only popularity score and interaction count.
- `liked_by_similar_users` — collaborative-filtering contribution or neighbor
  evidence.
- `extension_model_match` — LightGCN score evidence.
- `cold_start` — no eligible user history.

Planned endpoints:

- `GET /healthz`
- `GET /readyz`
- `POST /api/v1/recommendations`
- `POST /api/v1/feedback`
- `GET /api/v1/models`
- `GET /api/v1/models/current`
- `GET /metrics` if time permits

The recommendation request accepts `user_id`, `top_k` (10 by default),
`exclude_seen`, and optional `candidate_ids`. A response returns the user ID,
model identifier, requested top-K, ranked recommendations, a fallback indicator,
and generation time. The feedback endpoint records whether a displayed item was
clicked, played, skipped, or hidden.

The Next.js demo has five routes:

- `/` — user selection/input, cold-start toggle, top-K control, and
  recommendations.
- `/videos/[videoId]` — official video metadata, relevant categories, and
  similar-item explanation.
- `/compare` — popularity, item-CF, LightGCN, and hybrid results for the same
  user and candidates.
- `/metrics` — evaluation metrics and split summary.
- `/system` — active model manifest, dataset release, API status, and
  reproducibility information.

Feedback records displayed-item actions (for example clicked, played, skipped,
or hidden). It is not online learning unless a retraining path is actually built.

## Required artifacts

- **Data:** official release identifier/checksum, audit report and
  `docs/DATA_CARD.md`, filtered interactions, leakage-safe splits, candidate
  catalog, and split-specific user histories.
- **Models:** popularity, item-CF, LightGCN, hybrid weights, evaluation
  predictions, `model_manifest.json`, and reason-code configuration.
- **Software:** Go API, Next.js frontend, Python training source, Compose
  configuration, API specification, unit/integration tests, and smoke-test
  evidence.
- **Submission:** working system; 2–3-page report; presentation; README;
  architecture diagram; dataset/model comparison; example recommendation and
  explanation screenshots; limitations/risks; and demo/backup instructions.

The manifest must make the serving artifact auditable (model/configuration,
dataset release, preprocessing/split protocol, and artifact metadata/checksums).
Generated data and large checkpoints stay out of version control by default.

## Acceptance criteria

The project is accepted when:

- The exact official release, target, filters, split, candidate protocol, and
  checksums/version metadata are documented and reproducible.
- Test interactions cannot enter training/history used for final ranking or
  validation-based model selection.
- Popularity and item-CF are implemented; LightGCN is implemented and evaluated.
  Any fallback requires an explicit scope approval and must itself be evaluated.
- Hybrid weights and ablations are reproducible, validation-tuned, and reported
  honestly, including a null or negative result.
- The API returns top-K recommendations for known, cold-start, and unknown users,
  with seen-item behavior and evidence-backed explanations.
- The frontend exposes the agreed routes and usable desktop/mobile states.
- PostgreSQL-backed feedback survives a server restart; operational logs are
  queryable.
- Docker deployment starts from documented commands and passes a clean-restart
  smoke test.
- Metrics, model names, cards, report, slides, screenshots, and demo all agree
  with saved evaluation evidence.
- Both members have reviewed the final work; secrets and local absolute paths
  are absent; a cold-start demo and a backup plan are ready.

## Risks and controls

| Risk | Control / fallback |
|---|---|
| Official schema or target differs from assumptions | Verify the official documentation first; use a release-specific adapter and freeze the target before evaluation. |
| Dataset is too large for local training | Use a documented sample and report its coverage; do not imply full-release results. |
| Small Matrix is misused as an independent test | Follow the official protocol and document which data is used for training and evaluation. |
| LightGCN setup or results are unstable | Time-box it after baselines; keep the baseline results, record the failure, and request approval before changing the planned extension. |
| Hybrid overfits validation | Constrain weights, run a fixed validation grid, report ablations, and retain item-CF if it is better supported. |
| Backend artifact loading is too slow | Preload/index artifacts or precompute recommendation lists; report the actual serving design. |
| Explanation lacks model evidence | Persist contribution/evidence during ranking; omit unsupported reason text. |
| Schedule or UI scope grows | Preserve the one-extension limit and freeze core routes by Day 9; reduce screens before weakening evaluation. |
| Deployment dependency conflict | Pin versions, run clean-restart tests, and document local Go/Next.js startup as backup. |
