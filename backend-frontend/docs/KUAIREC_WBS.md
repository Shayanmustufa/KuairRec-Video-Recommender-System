# KuaiRec Recommendation System — 15-Day Work Breakdown Structure (WBS)

**Project Title**: Explainable Personalized Short-Video Recommendation Using Collaborative Filtering, Sequential Modeling, and Graph Signals  
**Team Members**:
- **Abdul Qadir Satti (23K-0674, BCS-7B)**: Backend API, Frontend UI, Explanations, Database, Docker, Integration & Presentation
- **Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)**: ML Modeling, Data Preprocessing, Temporal Split, Baselines, Offline Evaluation

---

## Tracking Board Summary (Abdul Qadir Satti's Workstream)

| Task ID | Day | Area | Description | Status |
|---|---|---|---|---|
| **AQ-01** | Day 1 | Architecture | Create Next.js and Go repository structure, Dockerfiles, env files | **IMPLEMENTED** |
| **AQ-02** | Day 1 | Documentation | Draft API contract and create project board columns | **PARTIAL** |
| **AQ-03** | Day 2 | Go Backend | Create typed Go domain types, req/resp structs, placeholder endpoints | **IMPLEMENTED; GO TEST PENDING** |
| **AQ-04** | Day 2 | Next.js Frontend | Create user selector and recommendation feed shell | **IMPLEMENTED; BUILD PASSED** |
| **AQ-05** | Day 2 | DevOps | Add Docker Compose services for API and frontend | **CONFIGURED; RUNTIME PENDING** |
| **AQ-06** | Day 3 | Go Backend | Implement artifact reader in Go, model manifest parser | **IMPLEMENTED** |
| **AQ-07** | Day 3 | Engine | Add validation for unknown users and unseen items, cold-start fallback | **IMPLEMENTED; GO TEST PENDING** |
| **AQ-08** | Day 3 | Next.js Frontend | Add frontend loading, empty, and error states | **IMPLEMENTED; BUILD PASSED** |
| **AQ-09** | Day 4 | Integration | Connect backend to popularity artifact, return ordered recommendations | **IMPLEMENTED** |
| **AQ-10** | Day 4 | UI/UX | Add frontend recommendation cards with skeleton and rank labels | **IMPLEMENTED** |
| **AQ-11** | Day 5 | API/Engine | Add recommendation source and score fields, error handling for unknown IDs | **IMPLEMENTED; GO TEST PENDING** |
| **AQ-12** | Day 5 | Testing | Implement unit and integration tests, latency display | **PARTIAL; GO TEST PENDING** |
| **AQ-13** | Day 6 | UI/UX | Create `/compare` route, video metadata cards, evidence panel | **IMPLEMENTED; BUILD PASSED** |
| **AQ-14** | Day 7 | Go Backend | Implement manifest switching and deterministic reason-code builders | **IMPLEMENTED; GO TEST PENDING** |
| **AQ-15** | Day 8 | Engine/API | Implement weighted hybrid artifact consumption, model comparison API data | **IMPLEMENTED** |
| **AQ-16** | Day 9 | Full UI | Complete all 5 routes (`/`, `/videos/[id]`, `/compare`, `/metrics`, `/system`) | **IMPLEMENTED; BUILD PASSED** |
| **AQ-17** | Day 10 | Persistence | Add PostgreSQL schema for feedback and recommendation logs, structured logs | **IMPLEMENTED; DB RUNTIME PENDING** |
| **AQ-18** | Day 10 | Observability | Add `/healthz`, `/readyz`, `/metrics`, request ID & latency middleware | **IMPLEMENTED; GO TEST PENDING** |
| **AQ-19** | Day 11 | QA/Testing | End-to-end integration tests, frontend responsive test, console error check | **UNVERIFIED** |
| **AQ-20** | Day 12 | Deployment | Finalize multi-stage Docker Compose, reverse proxy/CORS, clean restart | **CONFIGURED; RUNTIME PENDING** |
| **AQ-21** | Day 13 | UAT | 5 end-user test scenarios verified, mobile behavior checked | **UNVERIFIED; TEST PLAN UPDATED** |
| **AQ-22** | Day 14 | Presentation | Create presentation slides and step-by-step demo script | **PARTIAL; SCREENSHOT EVIDENCE PENDING** |
| **AQ-23** | Day 15 | Handoff | Final deployment smoke test, fallback plans, and delivery handoff | **UNVERIFIED** |

---

## Detailed Day-by-Day WBS Execution

### Day 1 — Project Kickoff, Dataset Approval, and Architecture
- **Syed Shayan Mustufa Rizvi**: Download official KuaiRec release, schema audit, temporary data card.
- **Abdul Qadir Satti**: Created Next.js + Go folder structure, Docker configs, `API_SPEC.md`, project board tracking.

### Day 2 — Dataset Audit and Preprocessing Pipeline
- **Syed Shayan Mustufa Rizvi**: Schema audit, ID normalization, duplicate detection, `DATA_CARD.md`.
- **Abdul Qadir Satti**: Typed Go domain models (`RecommendedItem`, `RecommendationRequest`), health and recommendation API shells, frontend user selector, Docker Compose skeleton.

### Day 3 — Leakage-Safe Splits and Model Artifacts
- **Syed Shayan Mustufa Rizvi**: 70/15/15 chronological temporal split, candidate catalog export.
- **Abdul Qadir Satti**: Go artifact reader (`testdata/catalog.json`, `testdata/model_manifest.json`), cold-start fallback trigger, UI loading/error states.

### Day 4 — Popularity Baseline
- **Syed Shayan Mustufa Rizvi**: Popularity baseline scoring ($log_{10}(\text{views}) \times \text{watch\_ratio}$).
- **Abdul Qadir Satti**: Connected backend to popularity artifact, created video cards with rank tags and server-side validation.

### Day 5 — Item-Based Collaborative Filtering
- **Syed Shayan Mustufa Rizvi**: Item-item cosine similarity with neighbor shrinkage, seen-item removal.
- **Abdul Qadir Satti**: Integrated source and score fields, error handling for unknown IDs, API response latency headers (`X-Response-Time-Ms`), and unit tests.

### Day 6 — Advanced Extension Prototype
- **Syed Shayan Mustufa Rizvi**: LightGCN bipartite graph model prototype.
- **Abdul Qadir Satti**: Built `/compare` route, recommendation evidence cards, and structured explanation schemas.

### Day 7 — Advanced Extension and Validation
- **Syed Shayan Mustufa Rizvi**: LightGCN hyperparameter tuning, embedding export.
- **Abdul Qadir Satti**: Implemented model manifest switching in Go (`POST /api/v1/models/switch`), deterministic explanation builders with reason codes, and UI badges.

### Day 8 — Hybrid Ranker
- **Syed Shayan Mustufa Rizvi**: Validation-selected weights are 0.90 Item-CF, 0.00 LightGCN, and 0.10 popularity; LightGCN is evaluated but rejected as a final component.
- **Abdul Qadir Satti**: Built weighted hybrid ranker consumption in Go, comparison API data, and frontend sorting controls.

### Day 9 — Final Explainable API and UI
- **Syed Shayan Mustufa Rizvi**: Reason-code rule definitions, model card draft.
- **Abdul Qadir Satti**: Completed all 5 frontend routes: `/`, `/videos/[videoId]`, `/compare`, `/metrics`, and `/system`. Added pagination and cold-start simulator.

### Day 10 — Database, Feedback, and Observability
- **Syed Shayan Mustufa Rizvi**: Final data statistics and model artifact metadata.
- **Abdul Qadir Satti**: PostgreSQL schema for feedback (`click`, `play`, `skip`, `hide`) and recommendation logs. Added `/healthz`, `/readyz`, `/metrics`, structured `log/slog`, and request UUID middleware. Runtime persistence still requires Compose verification.

### Day 11 — Evaluation and Test Freeze
- **Syed Shayan Mustufa Rizvi**: Evaluated test metrics (Recall, NDCG, Hit Rate, Precision, Coverage).
- **Abdul Qadir Satti**: Go tests and responsive layouts are present. Integration tests, Docker builds, and mobile behavior remain unverified in this workspace; see `ABDUL_WORK_AUDIT.md`.

### Day 12 — Deployment and Integration Testing
- **Syed Shayan Mustufa Rizvi**: Verified model manifest and dataset release in UI.
- **Abdul Qadir Satti**: Docker Compose configuration and clean-start instructions exist; actual image build/restart remains unverified.

### Day 13 — Failure Analysis and User Acceptance Testing
- **Syed Shayan Mustufa Rizvi**: Failure mode analysis (duplicates, popularity dominance).
- **Abdul Qadir Satti**: Five acceptance scenarios are listed but not observed in this workspace. Prior PASS statements were removed because their example users, model IDs, storage claim, and metric values did not match the serving artifacts.

### Day 14 — Report, Presentation, and Artifact Review
- **Syed Shayan Mustufa Rizvi**: Drafted methodology and ablation tables.
- **Abdul Qadir Satti**: Presentation outline, architecture guide, API contract, and demo runbook are present and corrected to match current artifacts. Screenshots and observed demo evidence are pending.

### Day 15 — Final Validation, Submission, and Handoff
- **Syed Shayan Mustufa Rizvi**: Checksums, reproducibility audit.
- **Abdul Qadir Satti**: Handoff runbook is present; deployment smoke and fallback verification are pending runtime evidence.
