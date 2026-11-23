# KuaiRec Recommendation System — API Specification

**Author / Backend Lead**: Abdul Qadir Satti (23K-0674, BCS-7B)  
**Partner / ML Lead**: Syed Shayan Mustufa Rizvi (23K-0924, BCS-7A)  
**Version**: 1.0.0  
**Protocol**: REST / HTTP JSON  
**Default Base URL**: `http://localhost:8080`

---

## 1. System Health & Observability

### 1.1 `GET /healthz`
Returns liveness status. Used by Docker Compose and container orchestrators.
- **Response**: `200 OK`
```json
{
  "status": "ok",
  "time": "2026-02-15T12:00:00Z"
}
```

### 1.2 `GET /readyz`
Returns readiness status, verifying that the catalog index and model manifests are loaded into memory.
- **Response**: `200 OK`
```json
{
  "status": "ready",
  "catalog_items": 20,
  "active_model": "hybrid-v1",
  "server_time": "2026-02-15T12:00:00Z"
}
```

### 1.3 `GET /metrics`
Returns real-time telemetry metrics: total requests handled, recommendation invocations, feedback counts, error counts, and average latency.
- **Response**: `200 OK`
```json
{
  "total_requests": 142,
  "recommendations_served": 88,
  "feedback_events_total": 45,
  "error_count": 0,
  "average_latency_ms": 1.15,
  "feedback_by_action": {
    "click": 18,
    "play": 21,
    "skip": 4,
    "hide": 2
  }
}
```

---

## 2. Core Recommendation Service

### 2.1 `POST /api/v1/recommendations`
Generates top-K video recommendations with evidence-based reason codes for a given user.

- **Request Headers**:
  - `Content-Type: application/json`
  - `X-Request-ID: <optional-uuid>`
- **Request Body**:
```json
{
  "user_id": "user_1001",
  "top_k": 10,
  "exclude_seen": true,
  "candidate_ids": null
}
```

- **Parameters**:
  - `user_id` (string, required): Unique identifier of user.
  - `top_k` (integer, optional, default: 10, max: 50): Number of ranked items to return.
  - `exclude_seen` (boolean, optional, default: true): If true, filters out items in user's interaction history.
  - `candidate_ids` (array of strings, optional): If provided, filters ranking to this subset of items.

- **Response `200 OK` (Personalized Hybrid)**:
```json
{
  "user_id": "user_1001",
  "model": "hybrid-v1",
  "top_k": 10,
  "recommendations": [
    {
      "item_id": "v_119",
      "rank": 1,
      "score": 0.884,
      "source": "hybrid",
      "video": {
        "item_id": "v_119",
        "title": "Unreal Engine 5 Next-Gen Graphics Showcase",
        "category": "Gaming",
        "duration_seconds": 48,
        "tags": ["gaming", "graphics", "unrealengine"],
        "author_id": "creator_99",
        "upload_date": "2026-01-31T16:00:00Z",
        "watch_ratio_avg": 1.45,
        "total_views": 275000
      },
      "reasons": [
        {
          "code": "similar_to_recent",
          "text": "Similar to video v_101 from your recent history",
          "evidence": {
            "item_id": "v_101",
            "similarity": 0.84
          }
        },
        {
          "code": "extension_model_match",
          "text": "High bipartite graph community alignment in LightGCN embeddings",
          "evidence": {
            "graph_score": 0.78,
            "layer_hop": 2
          }
        }
      ]
    }
  ],
  "fallback": false,
  "generated_at": "2026-02-15T12:00:01Z",
  "latency_ms": 1.25
}
```

- **Response `200 OK` (Cold-Start Fallback)**:
Triggered when user has 0 past interactions or is unknown.
```json
{
  "user_id": "user_cold_start",
  "model": "popularity-v1",
  "top_k": 10,
  "recommendations": [
    {
      "item_id": "v_108",
      "rank": 1,
      "score": 1.0,
      "source": "popularity-fallback",
      "reasons": [
        {
          "code": "cold_start",
          "text": "Curated top-performing video for new viewers (cold-start baseline)",
          "evidence": {
            "reason": "insufficient_user_history"
          }
        }
      ]
    }
  ],
  "fallback": true,
  "generated_at": "2026-02-15T12:00:01Z",
  "latency_ms": 0.82
}
```

---

## 3. Feedback Storage

### 3.1 `POST /api/v1/feedback`
Records implicit or explicit user interactions on recommended items.
- **Request Body**:
```json
{
  "user_id": "user_1001",
  "item_id": "v_119",
  "action": "play",
  "model_id": "hybrid-v1"
}
```
- **Validation**:
  - `action` must be one of: `click`, `play`, `skip`, `hide`.
- **Response**: `200 OK`
```json
{
  "status": "recorded",
  "user_id": "user_1001",
  "item_id": "v_119",
  "action": "play"
}
```

---

## 4. Models, Manifest & Administration

### 4.1 `GET /api/v1/models`
Returns list of registered models in the current system manifest.

### 4.2 `GET /api/v1/models/current`
Returns the active model metadata, dataset protocol, and fusion weights.

### 4.3 `POST /api/v1/models/switch`
Dynamically switches the active serving algorithm.
- **Request Body**:
```json
{
  "model_id": "itemcf-v1"
}
```
- **Response**: `200 OK`
```json
{
  "status": "updated",
  "current_model": "itemcf-v1"
}
```

---

## 5. Metadata & Multi-Model Comparison

### 5.1 `GET /api/v1/videos/{videoId}`
Returns full technical metadata for a specific short video.

### 5.2 `GET /api/v1/compare?user_id=user_1001&top_k=5`
Returns top-K recommendations for all 4 models (Popularity, Item-CF, LightGCN, Hybrid) simultaneously for side-by-side evaluation.

### 5.3 `GET /api/v1/users`
Returns list of pre-configured demo users and their cold-start statuses.

### 5.4 `GET /api/v1/metrics/offline`
Returns offline scientific benchmark evaluation tables (Recall, NDCG, Hit Rate, Coverage, Ablations).
