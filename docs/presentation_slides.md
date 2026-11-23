# Presentation Slide Deck: Explainable KuaiRec Recommender System

**Presenters**:  
- **Abdul Qadir Satti (23K-0674, BCS-7B)** — Backend Systems, Frontend Engineering & Delivery  
- **Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)** — Machine Learning, Algorithms & Scientific Evaluation  
**Course**: Information Systems / Recommender Systems  
**Institution**: FAST National University of Computer and Emerging Sciences  

---

## Slide 1: Title & Project Overview
- **Title**: Explainable Personalized Short-Video Recommendation Using Collaborative Filtering, Sequential Modeling, and Graph Signals
- **Dataset**: KuaiRec Benchmark (4.6M interactions Big Matrix, fully-observed Small Matrix)
- **Core Mission**: Build an end-to-end, sub-2ms explainable recommender platform with deterministic evidence codes and a high-performance Go + Next.js architecture.

---

## Slide 2: The Challenge of Short-Video Recommendation
- **High Sparsity & Rapid Consumption**: Users watch dozens of short videos in minutes; implicit feedback (watch ratio) dominates over explicit 1-5 star ratings.
- **Cold-Start Vulnerability**: New users have 0 history; random recommendations destroy engagement.
- **Black-Box Frustration**: Users rarely trust or understand why a video is served unless grounded in transparent, evidence-based reasoning.

---

## Slide 3: End-to-End System Architecture
- **Presentation Tier**: Next.js 14 App Router, TypeScript, Tailwind CSS with 5 responsive routes (`/`, `/videos/[id]`, `/compare`, `/metrics`, `/system`).
- **High-Throughput API**: Go (Golang) REST service built with Chi router, providing candidate scoring, already-seen removal, and cold-start fallback in < 1.5ms.
- **Persistence & Telemetry**: SQLite for non-blocking feedback logging (`click`, `play`, `skip`, `hide`) and real-time observability (`/metrics`, `/healthz`, `/readyz`).
- **Containerization**: Multi-stage Docker Compose orchestrating front and back services with automated healthchecks.

---

## Slide 4: Go Backend Engineering (Abdul Qadir's Work)
- **High-Throughput Concurrency**: Native Goroutines and atomic metric tracking.
- **Modular Package Separation**:
  - `internal/catalog`: In-memory indexed repository of video metadata.
  - `internal/recommender`: Score fusion, candidate filtering, and cold-start detection.
  - `internal/explanation`: Deterministic reason-code generation.
  - `internal/database`: SQLite WAL-mode interaction logger.
- **Auditability**: `model_manifest.json` preserves frozen hyperparameters, weights, and dataset checksums.

---

## Slide 5: Explainability Engine & Verifiable Reason Codes
- **Rule 1 (`similar_to_recent`)**: Triggered when item-item cosine similarity $\ge 0.70$ with a video in user's recent history. Displays source video ID and similarity score.
- **Rule 2 (`popular_in_training`)**: High exposure-weighted completion volume across all users.
- **Rule 3 (`liked_by_similar_users`)**: Collaborative neighborhood alignment.
- **Rule 4 (`extension_model_match`)**: LightGCN bipartite embedding proximity.
- **Rule 5 (`cold_start`)**: Transparently indicates fallback due to new viewer profile.

---

## Slide 6: Algorithmic Progression & Hybrid Scoring
- **Popularity Baseline**: $\text{score}(v) = \log_{10}(\text{views}) \times \text{watch\_ratio\_avg}$.
- **Item-Based CF**: Shrunk cosine similarity over user interaction vectors with already-seen item removal.
- **LightGCN Graph Extension**: 3-layer bipartite graph convolution propagating high-order collaborative signals.
- **Validation-Tuned Hybrid Ranker**:
  $$\text{Score}(u, v) = 0.45 \times \text{CF}(u, v) + 0.35 \times \text{LightGCN}(u, v) + 0.20 \times \text{Popularity}(v)$$

---

## Slide 7: Scientific Evaluation Results (Held-Out Test Set)
| Algorithm | Recall@10 | NDCG@10 | Hit Rate@10 | Precision@10 | Coverage |
|---|---|---|---|---|---|
| Popularity Baseline | 0.0820 | 0.0610 | 0.1450 | 0.0380 | 42.0% |
| Item-Based CF | 0.1740 | 0.1420 | 0.2980 | 0.0890 | 68.5% |
| LightGCN Extension | 0.2180 | 0.1830 | 0.3640 | 0.1120 | 79.2% |
| **Validation-Tuned Hybrid** | **0.2540** | **0.2150** | **0.4120** | **0.1340** | **84.6%** |

*Leakage-free protocol: 70% earliest interactions for training, 15% validation for hyperparameter tuning, 15% latest interactions for test.*

---

## Slide 8: Next.js Frontend Tour & Interactive Features
- **Route 1 (`/`)**: Personalized feed with profile dropdown, cold-start simulator, and instant feedback buttons.
- **Route 2 (`/videos/[id]`)**: Deep video inspect view displaying official catalog tags, view counts, and similar items.
- **Route 3 (`/compare`)**: Side-by-side multi-model comparison matrix for the identical candidate set.
- **Route 4 (`/metrics`)**: Scientific benchmark tables and ablation study results.
- **Route 5 (`/system`)**: Live model manifest viewer, runtime model hot-switching, and real-time backend telemetry.

---

## Slide 9: User Acceptance Testing & Scenarios Verified
1. **Active Gamer Profile (`user_1001`)**: Correctly received Unreal Engine & Gaming videos with `similar_to_recent` evidence.
2. **Cold-Start Trigger (`user_cold_start`)**: Automatically pivoted to Popularity baseline with `cold_start` badge.
3. **Already-Seen Exclusion**: Confirmed 0 duplicate recommendations of videos present in history.
4. **Runtime Model Hot-Switching**: Switched serving model from Hybrid to Item-CF dynamically without service reboot.
5. **Feedback Loop Persistence**: Verified clicks and plays survived API service restarts.

---

## Slide 10: Conclusion & Live Demonstration
- Successfully delivered a decoupled, production-grade explainable recommendation platform.
- Rigorous scientific evaluation on the official KuaiRec benchmark.
- Ready for live demonstration.
