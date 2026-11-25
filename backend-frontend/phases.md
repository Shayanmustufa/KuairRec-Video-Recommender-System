# Implementation Phases

This plan follows the supplied 15-day WBS in relative day order. Per request, it
does not assign calendar dates. The phase boundaries group related work; they do
not change the day-level ownership or exit criteria in the WBS.

## Team ownership and review rule

- **Syed Shayan Mustufa Rizvi (23K-0924):** data, training, recommendation
  algorithms, experiment design, and scientific evaluation.
- **Abdul Qadir Satti (23K-0674):** backend/API, frontend/demo, explanations,
  integration, deployment, and presentation.
- The primary owner implements; the other member reviews using code, tests,
  reproducible outputs, or observed behavior. Both share architecture decisions,
  final review, interpretation, report quality, security/secret checks, and
  acceptance testing. Approval is evidence-based, not verbal only.

## Phase 1 — Project kickoff and data foundation (Days 1–3)

**Goal:** agree on scope and contracts, verify the official data, produce
reproducible leakage-safe splits, and have runnable application shells.

**Syed's Phase 1 status:** complete. The official archive was checksum-verified;
the audit/data card, split artifacts, and automated tests are available as
described in [model/README.md](./model/README.md) and
[docs/DATA_CARD.md](./docs/DATA_CARD.md). Abdul's parallel Phase 1 work is not
claimed as completed by this implementation.

### Syed Shayan Mustufa Rizvi

- **Day 1:** download/verify the official KuaiRec release, README, schema,
  permitted-use terms, timestamps, engagement semantics, and social-link schema;
  start the data card; define provisional eligibility and target options; decide
  the popularity baseline and LightGCN scope.
- **Day 2:** implement schema/data audit; normalize IDs; measure missing values,
  duplicates, unique users/videos, interaction counts before/after filtering,
  timestamp range, engagement range/distribution, catalog size, category counts,
  sparsity, train/evaluation overlap, and social-link count if used; save
  statistics and sample records; document release ID/checksum and finalized
  preprocessing in `docs/DATA_CARD.md`.
- **Day 3:** implement chronological train/validation/test split; freeze seed and
  boundaries; export split files, candidate catalog, and split-specific user
  history; verify disjointness and add split unit tests.

### Abdul Qadir Satti

- **Day 1:** establish Go and Next.js repository structure; configure linting,
  formatting, Docker, and environment files; draft API contract and UI wireframes;
  create project-board columns (`Backed Up`, `Planned`, `In Progress`, `Review`,
  `Blocked`, `Done`); document reproducibility/run expectations.
- **Day 2:** define typed Go domain and API request/response types; add placeholder
  health and recommendation endpoints; create the user selector and empty-result
  shell; add API/frontend Docker Compose services.
- **Day 3:** implement the Go artifact reader and model-manifest format; validate
  unknown users/unseen items; define cold-start endpoint behavior; add frontend
  loading, empty, and error states.

### Shared review, deliverables, and gate

- Abdul reviews the official release record, schema adapter, and data assumptions;
  Syed reviews the API contract and application skeleton.
- **Deliverables:** approved data protocol and architecture, audit report,
  typed API contract, split artifacts, runnable API/frontend shells, and
  manifest-aware loader.
- **Exit gate:** release and target definition are documented; repository builds;
  split boundaries and disjointness are tested; the API contract compiles; both
  members approve the model scope. No test interaction may occur in training
  history used for final ranking.

## Phase 2 — Baselines and first end-to-end recommendation (Days 4–5)

**Goal:** deliver popularity and item-CF as evaluated models usable through the
API and browser.

**Syed's Phase 2 status:** Days 4–5 complete. The training-only positive-event popularity
baseline, cold-start artifact, full-catalog validation predictions, metrics,
per-user examples, checksums, and tests are reproducible. Item-CF cosine
similarities, shrinkage/neighborhood tuning, selected artifacts, validation
comparison, and the honest negative primary-metric result are documented in
[docs/EXPERIMENTS.md](./docs/EXPERIMENTS.md).

### Syed Shayan Mustufa Rizvi

- **Day 4:** implement the training-only popularity scorer, ranking, and
  evaluation; configure event relevance and popularity weighting; save validation
  predictions/metrics and per-user examples.
- **Day 5:** build item-item cosine/positive-signal similarities; implement
  shrinkage/configurable similarity, item-CF ranking, and seen-item removal; tune
  neighborhood/similarity on validation only; save artifact and metrics.

### Abdul Qadir Satti

- **Day 4:** load/serve the popularity artifact; implement ordered results and
  cold-start fallback; add recommendation cards, rank labels, loading skeleton,
  and request validation.
- **Day 5:** expose source and score; create model-comparison state; handle
  unknown IDs; add API integration tests and latency display.

### Shared review, deliverables, and gate

- **Deliverables:** end-to-end popularity recommendation; item-CF artifact,
  metrics, and integrated API response.
- **Exit gate:** a selected user can receive top-K recommendations in the browser;
  item-CF either beats popularity on validation or the reason is documented.

## Phase 3 — LightGCN and validation-tuned hybrid (Days 6–8)

**Goal:** evaluate the single planned advanced model and combine model signals
without using test data for selection.

**Syed's Phase 3 status:** Days 6–8 complete. The frozen small-sample LightGCN prototype,
BPR training, finite-value checks, debug validation, checkpoint, predictions,
checksums, and regression test are reproducible. Day 7 validation-only tuning
selected and retrained a full-graph configuration, exported embeddings and
predictions, and compared it with both frozen baselines. LightGCN is stable but
underperforms both baselines on every ranking metric, so it is rejected as the
standalone model. With explicit scope approval, Day 8 evaluated the planned
three-component hybrid while allowing zero weights. Validation selected 0.1
popularity + 0.9 Item-CF + 0.0 LightGCN; all 66 weight combinations and
ablations are reproducible in [docs/EXPERIMENTS.md](./docs/EXPERIMENTS.md).

### Syed Shayan Mustufa Rizvi

- **Day 6:** prototype LightGCN on the sparse user-video interaction graph; freeze
  initial seed/hyperparameters and validate on a small debugging sample.
- **Day 7:** tune only learning rate, propagation layers, embedding size, and
  epochs on validation; export embeddings/scores; compare to both baselines;
  stop if results are unstable or degrade; document rejected experiments.
- **Day 8:** normalize item-CF, LightGCN, and popularity scores; search
  nonnegative weights summing to one on validation; document constraints,
  candidate construction, and hybrid ablations.

### Abdul Qadir Satti

- **Day 6:** create comparison route, official-metadata video cards/placeholders,
  and recommendation-evidence panel; draft explanation data structure.
- **Day 7:** implement manifest/model switching in Go; build deterministic
  explanation builders and UI source attribution; add cache/preload only if
  measurements justify it.
- **Day 8:** consume hybrid artifacts in Go; expose comparison data; create hybrid
  explanation panel and frontend sorting/refresh controls.

### Shared review, deliverables, and gate

- **Deliverables:** LightGCN validation report and export; reproducible
  validation-tuned hybrid and ablation table; model switching and explanation
  evidence in the demo.
- **Exit gates:** LightGCN outputs are finite, trained without leakage, and
  evaluated; hybrid weights are reproducible and test metrics have not influenced
  selection. If LightGCN is blocked, stop and record the evidence; request
  approval before changing scope, and do not pass this gate until the approved
  model has been evaluated.

## Phase 4 — Explainable product, persistence, and operations (Days 9–10)

**Goal:** complete the core demo experience and persist operational/user feedback
data without implying online model learning.

**Syed's Phase 4 status:** Days 9–10 complete. The tracked reason-code contract, evidence
generator, fail-closed validation across all 143,520 validation recommendations,
draft model card, and checksum-based test-time freeze are complete. Day 10
consolidated final data statistics, inventoried 25 artifacts, created the
reproduction table, and passed the formal leakage audit with zero chronological
violations. No test metric has been calculated. See
[docs/MODEL_CARD.md](./docs/MODEL_CARD.md) and
[docs/REPRODUCIBILITY.md](./docs/REPRODUCIBILITY.md).

### Syed Shayan Mustufa Rizvi

- **Day 9:** define reason-code rules; verify every explanation has corresponding
  model evidence; draft `docs/MODEL_CARD.md`; freeze test-time artifacts.
- **Day 10:** prepare final data statistics and artifact metadata; create the
  experiment/reproducibility table; review leakage checks.

### Abdul Qadir Satti

- **Day 9:** complete recommendation, comparison, metrics, and system routes;
  add pagination/top-K controls and no-history/unknown-user states; check basic
  keyboard accessibility; handle loading, timeout, and backend-unavailable states.
- **Day 10:** add PostgreSQL schema and persistence for requests, feedback, and
  recommendation metadata; add structured logs, request IDs, and latency
  middleware; expose `/healthz`, `/readyz`, and `/metrics` if time permits; add
  CORS and rate limiting.

### Shared review, deliverables, and gate

- **Deliverables:** complete explainable API/UI; finalized reason/evidence
  contract; persistent feedback and queryable logs.
- **Exit gates:** recommendations and visible evidence work in one browser
  session; feedback survives a server restart; logs are queryable. Feedback is
  not described as online learning unless model retraining exists.

## Phase 5 — Frozen evaluation, deployment, and acceptance testing (Days 11–13)

**Goal:** produce final controlled test evidence, a clean deployment, and
documented failure/acceptance results.

### Syed Shayan Mustufa Rizvi

- **Day 11:** run one controlled test pass; calculate Recall@10/20, NDCG@10/20,
  Hit Rate@10, Precision@10, and coverage; check cold-start and seen items;
  record runtime, hardware, and seed. Do not change the model after this pass
  except to fix a confirmed reproducibility bug.
- **Day 12:** finalize `docs/MODEL_CARD.md`; verify model manifest and dataset
  release are visible in the UI; review ablations and remove unsupported claims.
- **Day 13:** inspect recommendations for duplicates, popularity dominance, and
  cold-start behavior; create a failure table; run stability checks across seeds;
  document bias and catalog-coverage limitations.

### Abdul Qadir Satti

- **Day 11:** run API integration tests and frontend unit/component tests; verify
  Docker build; add Playwright smoke coverage if setup permits; check mobile
  behavior and browser-console errors.
- **Day 12:** finalize Compose deployment for frontend and Go API; verify
  reverse-proxy/CORS/environment configuration; test clean restart and document
  deployment commands.
- **Day 13:** run at least five end-user scenarios; verify routes and mobile
  behavior; fix display, timeout, empty-state, and accessibility issues; capture
  screenshots/demo evidence.

### Shared review, deliverables, and gate

- **Deliverables:** final experiment table and baseline system tests; dockerized
  app; failure analysis, known limitations, and acceptance evidence.
- **Exit gates:** test metrics reproduce from saved artifacts/scripts; clean
  restart succeeds; critical acceptance scenarios pass.

## Phase 6 — Reporting, submission, and handoff (Days 14–15)

**Goal:** submit a reproducible, internally consistent implementation and
evidence-backed demonstration with a working fallback.

### Syed Shayan Mustufa Rizvi

- **Day 14:** write methodology, data card, experimental setup, results,
  ablations, and limitations; prepare metric tables/charts; cite official KuaiRec
  sources and relevant algorithm papers.
- **Day 15:** run final reproducibility and leakage audits; archive split
  statistics and model artifacts; generate SHA-256 checksums where practical;
  prepare the final results appendix.

### Abdul Qadir Satti

- **Day 14:** record demo flow/screenshots; create presentation slides; document
  architecture/API; prepare concise explanations for each demo screen.
- **Day 15:** run final deployment smoke test; freeze Compose/images; prepare
  backup run instructions/screenshots; test startup on a second machine if
  available; prepare talking points and fallback plans.

### Shared work, deliverables, and gate

- **Day 14:** reproduce the final command set; verify team names/IDs; review
  spelling, formulas, citations, screenshots, and result disagreements.
- **Day 15:** final code review; remove secrets/temporary credentials; verify
  README commands; submit source, report, presentation, and demo evidence; rehearse
  known-user and cold-start demonstrations.
- **Deliverables:** presentation-ready report, slides, demo script, source,
  evidence, and handoff instructions.
- **Exit gate:** no critical bug remains; every claim is supported by saved
  evidence; model names/metrics agree across code, UI, report, and slides; demo
  works independently of the development machine or has a documented fallback.

## Cross-phase definition of done

Before any work item is marked complete, it must be saved in the repository,
tested or backed by a reproducible observed result, documented where user-visible,
and reviewed by the other member. Errors and empty states must be handled; no
secrets or local absolute paths may be committed; the README must provide the
relevant run command; and experimental artifacts must either be used in the demo
or explicitly labeled experimental.
