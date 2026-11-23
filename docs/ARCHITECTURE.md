# System Architecture & Technical Design Document

**System Title**: Explainable Personalized Short-Video Recommendation System (KuaiRec Benchmark)  
**Lead Engineer (Systems & Frontend)**: Abdul Qadir Satti (23K-0674, BCS-7B)  
**Collaborator (Machine Learning & Data)**: Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)  

---

## 1. Architectural Overview

The KuaiRec Recommender platform is built on a decoupled, production-grade microservices architecture:
1. **Frontend Presentation Tier**: Next.js 14 (React, TypeScript, Tailwind CSS) providing a multi-view dashboard, interactive user selector, cold-start simulator, model comparison matrix, evaluation analytics, and real-time feedback triggers.
2. **Backend API Tier**: High-throughput Go (Golang) REST API providing sub-2ms ranking inference, already-seen candidate filtering, cold-start fallback detection, deterministic explanation synthesis, and live telemetry.
3. **Persistence Tier**: SQLite database storing API access logs, recommendation audit trails, and implicit user interactions (clicks, plays, skips, hides).
4. **Offline ML Pipeline**: Offline Python data engineering producing validated candidate indices, item-item similarity matrices, graph embeddings, and an auditable `model_manifest.json`.

```
                  ┌────────────────────────────────────────┐
                  │      Next.js 14 React Web Client       │
                  │ (Port 3000: Feed, Compare, Metrics)   │
                  └───────────────────┬────────────────────┘
                                      │ HTTP / JSON
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          Go Chi REST API               │
                  │    (Port 8080: Middleware & Telemetry) │
                  └──────┬────────────┬────────────┬───────┘
                         │            │            │
            ┌────────────▼───┐ ┌──────▼─────┐ ┌────▼──────────┐
            │ Recommender    │ │ Reason     │ │ Catalog       │
            │ Engine         │ │ Explainer  │ │ Repository    │
            └──────┬─────────┘ └──────┬─────┘ └───────────────┘
                   │                  │
            ┌──────▼──────────────────▼──────┐
            │ SQLite Database Storage        │
            │ (feedback_events, rec_logs)    │
            └────────────────────────────────┘
```

---

## 2. Go Backend Design (`backend/`)

### 2.1 Package Architecture
- `cmd/api/main.go`: Application entrypoint, graceful OS signal trapping (`SIGINT`, `SIGTERM`), server timeout management.
- `internal/config/config.go`: Environment variable resolution with defaults (`PORT`, `DATA_DIR`, `DB_PATH`, `DEFAULT_TOP_K`).
- `internal/catalog/catalog.go`: Thread-safe in-memory cache of video metadata indexed by `item_id`.
- `internal/explanation/explanation.go`: Deterministic factory for approved reason codes:
  - `similar_to_recent`: Item similarity above threshold and source item in history.
  - `popular_in_training`: Training popularity score and completion count.
  - `liked_by_similar_users`: CF collaborative neighborhood alignment.
  - `extension_model_match`: LightGCN graph bipartite embedding similarity.
  - `cold_start`: Baseline fallback for users lacking interaction history.
- `internal/recommender/recommender.go`: Candidate scoring, already-seen exclusion, percentile fusion, and cold-start fallback.
- `internal/database/db.go`: SQLite WAL-mode interaction logger with thread-safe in-memory fallback.
- `internal/telemetry/telemetry.go`: Atomic metrics counters (`TotalRequests`, `RecommendationsServed`, `FeedbackEvents`, `AverageLatency`) and UUID request tracing.
- `internal/httpapi/`: REST routing, CORS headers, JSON serialization, and route handlers.

### 2.2 Recommendation & Cold-Start Logic
When `POST /api/v1/recommendations` is called:
1. User history is retrieved from the indexed history store.
2. If `history == nil` or `len(history) == 0`:
   - System triggers cold-start fallback (`fallback = true`).
   - Serves videos ordered by global exposure-weighted completion volume (`popularity-v1`).
   - Reason code generated: `cold_start`.
3. If user is known:
   - System filters out items already engaged if `exclude_seen == true`.
   - Executes score evaluation under the requested algorithm (`popularity-v1`, `itemcf-v1`, `lightgcn-v1`, or `hybrid-v1`).
   - For `hybrid-v1`, fuses normalized scores using validation-tuned weights:
     $$\text{Hybrid}(u, v) = 0.45 \times \text{CF}(u, v) + 0.35 \times \text{LightGCN}(u, v) + 0.20 \times \text{Pop}(v)$$
   - Attach verified explanation evidence (source video ID and cosine similarity).
   - Truncates to requested `top_k`.

---

## 3. Frontend Architecture (`frontend/`)

Built using Next.js 14 App Router, TypeScript, and Tailwind CSS. Structured across 5 dedicated routes:

| Route | Purpose | Key Components |
|---|---|---|
| `/` | Live Feed & Interactive Sandbox | User profile selector, Cold-start toggle, Top-K buttons, Video cards, Feedback buttons |
| `/videos/[videoId]` | Video Deep Dive & Explainability | Technical metadata, tags, watch ratios, and similar item co-occurrence |
| `/compare` | Multi-Model Head-to-Head Matrix | Side-by-side columns comparing Popularity, Item-CF, LightGCN, and Hybrid |
| `/metrics` | Scientific Evaluation Dashboard | Recall@K, NDCG@K, Hit Rate, Precision, Coverage tables, and ablation study |
| `/system` | Architecture, Manifest & Telemetry | Live model manifest, active model hot-switching, live API counters, and latency |

---

## 4. Observability and Feedback Persistence

### 4.1 Real-Time Telemetry
Every API invocation traverses:
1. `RequestIDMiddleware`: Generates or extracts `X-Request-ID`.
2. `LatencyAndMetricsMiddleware`: Measures duration in microseconds and exposes `X-Response-Time-Ms`.
3. `LoggingMiddleware`: Emits structured JSON logs via standard Go `log/slog`.

### 4.2 Feedback Loop
When users interact with recommendation cards in the browser (clicking **Play**, **Click**, **Skip**, or **Hide**), the Next.js client dispatches an async request to `POST /api/v1/feedback`. The Go backend records this event to the SQLite database without blocking the client.

---

## 5. Deployment and Containerization

The system is fully containerized using multi-stage Docker builds:
- **Backend Container**: Multi-stage `golang:1.22-alpine` builder producing a stripped ~15MB static binary running on `alpine:3.19`.
- **Frontend Container**: Standalone Node.js production runner (`node:20-alpine`) with optimized assets.
- **Docker Compose**: Orchestrates both containers with internal networking, shared SQLite persistent volume, and automatic healthcheck dependency.
