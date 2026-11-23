# KuaiRec Recommender System — Live Demonstration Script

**Presenter**: Abdul Qadir Satti (23K-0674, BCS-7B)  
**Target Audience**: Course Instructors, Project Evaluators, and Peer Engineers  
**Time Limit**: 8–10 Minutes  

---

## 1. Setup & Pre-Flight Checklist (1 Minute Before Start)
1. Ensure the Go API backend is running (`cd backend && go run ./cmd/api` or Docker container).
2. Ensure the Next.js frontend is running (`cd frontend && npm run dev` on port 3000).
3. Open browser at `http://localhost:3000`.
4. Verify the top navbar displays a green **"Healthy (< 2ms)"** status pill.

---

## 2. Step-by-Step Demo Walkthrough

### Step 1: System Introduction & Architectural Flow (1 Minute)
- **Spoken Talking Point**:
  > "Good morning/afternoon. Today I am presenting the explainable short-video recommendation system built on the KuaiRec dataset. My primary responsibility as systems lead was developing the production Go REST API, the explainability reason-code pipeline, SQLite interaction persistence, and the Next.js frontend interface."
- **Action**: Navigate to `http://localhost:3000/system`.
- **Key Display**: Point out the live telemetry counters (API invocations, recommendations served, and sub-2ms response latency) and the official KuaiRec release manifest.

### Step 2: Personalized Feed & Known User Experience (2 Minutes)
- **Spoken Talking Point**:
  > "Let's begin on the main recommendation feed (`/`). Here we have selected user `user_1001`, an active user with past viewing history in Gaming and Technology. When we request Top-10 recommendations, the Go backend queries our hybrid ranker."
- **Action**: Return to `/`. Select `user_1001` from the dropdown. Keep "Exclude Already Seen" checked.
- **Key Display**:
  - Show the top-ranked item: `v_119` (Unreal Engine 5 Graphics Showcase).
  - Point out the **Reason Badge**: `"Similar to video v_101 from your recent history"` with machine-readable evidence: `similarity: 0.840`.
  - Explain: "Notice how this isn't a black box. The user immediately understands why this video was recommended based on actual cosine similarity to their previous watch."

### Step 3: Interactive User Feedback Loop (1 Minute)
- **Spoken Talking Point**:
  > "In short-video applications, user interaction happens in real-time. On any video card, a user can mark an action: Play, Click, Skip, or Hide. Let's click 'Play' on Rank #1."
- **Action**: Click the **Play** button on the first card.
- **Key Display**:
  - A green badge appears: `✓ Logged: play`.
  - Open `/system` in a second tab to show the "Feedback Events Recorded" counter increments immediately.
  - Explain: "This feedback is asynchronously dispatched to `POST /api/v1/feedback` and stored into our SQLite database, providing the auditable event log required for future model retraining."

### Step 4: Cold-Start Fallback Demonstration (1.5 Minutes)
- **Spoken Talking Point**:
  > "A critical requirement in recommender design is handling the cold-start problem: what happens when a brand-new user arrives with zero history? Rather than crashing or serving arbitrary ungrounded results, our backend automatically detects the zero-interaction state and pivots to an exposure-weighted popularity baseline."
- **Action**: Toggle the **"Force Cold-Start Fallback"** checkbox on the feed (or choose `user_cold_start`).
- **Key Display**:
  - The status bar updates to: `Fallback Triggered: YES (Cold Start Baseline)`.
  - The serving model changes to `popularity-v1`.
  - The reason codes update to: `"Curated top-performing video for new viewers (cold-start baseline)"`.

### Step 5: Head-to-Head Algorithm Comparison (1.5 Minutes)
- **Spoken Talking Point**:
  > "To verify that our algorithms behave distinctly, I developed the `/compare` route. This route simultaneously projects recommendations for the exact same user across all four models: Popularity Baseline, Item-Based CF, LightGCN Graph, and our Validation-Tuned Hybrid."
- **Action**: Click **"Model Comparison"** in the top navigation bar (`/compare`).
- **Key Display**:
  - Point out how **Popularity** serves the most viewed videos overall (e.g. Golden Retriever puppy).
  - Point out how **Item-CF** focuses on direct cosine neighbors in Gaming.
  - Point out how **LightGCN** uses 3-hop graph propagation to balance exploration and relevance.
  - Point out how **Hybrid** achieves optimal balance, blending CF precision with graph exploration.

### Step 6: Scientific Evaluation & Ablation Dashboard (1 Minute)
- **Spoken Talking Point**:
  > "Finally, let's examine the scientific evaluation page (`/metrics`). All models were strictly evaluated using a leakage-free temporal split on KuaiRec: 70% earliest events for training, 15% intermediate for validation tuning, and 15% latest events strictly held out for testing. As seen here, our validation-tuned hybrid model achieves the highest Recall@10 of 0.2540 and NDCG@10 of 0.2150, outperforming both baselines."
- **Action**: Click **"Evaluation & Ablations"** (`/metrics`).
- **Key Display**: Point to the summary table and the hybrid ablation grid ($\alpha=0.45, \beta=0.35, \gamma=0.20$).

---

## 3. Anticipated Questions and Strong Answers

**Q1: How does your Go API communicate with the machine learning models?**  
*Answer*: "Our Go backend loads the precomputed, offline-trained model artifacts—specifically the video catalog, item similarity matrices, user history vectors, and the auditable `model_manifest.json` exported by our Python pipeline. This ensures zero Python runtime overhead during serving, allowing our Go service to handle requests in under 2 milliseconds."

**Q2: How do you guarantee that reason codes are faithful and not hallucinated?**  
*Answer*: "Every explanation reason code is generated deterministically by `internal/explanation` based on the exact inputs that produced the rank. If an item is recommended via CF, it requires an item similarity score $\ge 0.40$ and points to the specific historical video ID in the user's trajectory. We strictly forbid ungrounded LLM text generation."

**Q3: How are seen videos filtered?**  
*Answer*: "When a recommendation request specifies `exclude_seen: true`, the engine builds a hash set of all item IDs present in the user's interaction history and removes them from the candidate pool prior to top-K sorting."
