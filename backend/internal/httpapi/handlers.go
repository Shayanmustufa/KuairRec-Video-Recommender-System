package httpapi

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

type Handler struct {
	engine   *recommender.Engine
	catalog  *catalog.Repository
	db       *database.DB
	dataDir  string
}

func NewHandler(engine *recommender.Engine, catalog *catalog.Repository, db *database.DB, dataDir string) *Handler {
	return &Handler{
		engine:  engine,
		catalog: catalog,
		db:      db,
		dataDir: dataDir,
	}
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

// GET /healthz
func (h *Handler) Healthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}

// GET /readyz
func (h *Handler) Readyz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":          "ready",
		"catalog_items":   h.catalog.Count(),
		"active_model":    h.engine.GetActiveModel(),
		"server_time":     time.Now().UTC().Format(time.RFC3339),
	})
}

// GET /metrics
func (h *Handler) Metrics(w http.ResponseWriter, r *http.Request) {
	feedbackStats, _ := h.db.GetFeedbackSummary(r.Context())
	totalReqs := telemetry.GlobalMetrics.TotalRequests.Load()
	totalLat := telemetry.GlobalMetrics.TotalLatencyMs.Load()
	avgLatency := 0.0
	if totalReqs > 0 {
		avgLatency = float64(totalLat) / float64(totalReqs)
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"total_requests":          totalReqs,
		"recommendations_served":  telemetry.GlobalMetrics.RecommendationsCount.Load(),
		"feedback_events_total":   telemetry.GlobalMetrics.FeedbackCount.Load(),
		"error_count":             telemetry.GlobalMetrics.ErrorCount.Load(),
		"average_latency_ms":      avgLatency,
		"feedback_by_action":      feedbackStats,
	})
}

// POST /api/v1/recommendations
func (h *Handler) Recommend(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var req recommender.RecommendationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON payload: "+err.Error())
		return
	}

	if strings.TrimSpace(req.UserID) == "" {
		writeError(w, http.StatusBadRequest, "Missing required field: user_id")
		return
	}

	resp, err := h.engine.Recommend(req)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Recommendation failure: "+err.Error())
		return
	}

	telemetry.GlobalMetrics.RecommendationsCount.Add(1)
	reqID := r.Header.Get("X-Request-ID")
	_ = h.db.LogRecommendation(r.Context(), reqID, req.UserID, resp.Model, resp.TopK, resp.Fallback)

	writeJSON(w, http.StatusOK, resp)
}

type FeedbackRequest struct {
	UserID  string `json:"user_id"`
	ItemID  string `json:"item_id"`
	Action  string `json:"action"` // "click", "play", "skip", "hide"
	ModelID string `json:"model_id"`
}

// POST /api/v1/feedback
func (h *Handler) Feedback(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var req FeedbackRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON payload: "+err.Error())
		return
	}

	if req.UserID == "" || req.ItemID == "" || req.Action == "" {
		writeError(w, http.StatusBadRequest, "Missing required fields: user_id, item_id, action")
		return
	}

	allowedActions := map[string]bool{"click": true, "play": true, "skip": true, "hide": true}
	if !allowedActions[req.Action] {
		writeError(w, http.StatusBadRequest, "Invalid action. Must be click, play, skip, or hide")
		return
	}

	if req.ModelID == "" {
		req.ModelID = h.engine.GetActiveModel()
	}

	if err := h.db.LogFeedback(r.Context(), req.UserID, req.ItemID, req.Action, req.ModelID); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to record feedback")
		return
	}

	telemetry.GlobalMetrics.FeedbackCount.Add(1)
	writeJSON(w, http.StatusOK, map[string]any{
		"status":  "recorded",
		"user_id": req.UserID,
		"item_id": req.ItemID,
		"action":  req.Action,
	})
}

// GET /api/v1/models
func (h *Handler) ListModels(w http.ResponseWriter, r *http.Request) {
	manifest := h.engine.GetManifest()
	writeJSON(w, http.StatusOK, map[string]any{
		"models":        manifest.Models,
		"current_model": manifest.CurrentModel,
	})
}

// GET /api/v1/models/current
func (h *Handler) CurrentModel(w http.ResponseWriter, r *http.Request) {
	manifest := h.engine.GetManifest()
	writeJSON(w, http.StatusOK, manifest)
}

type SwitchModelRequest struct {
	ModelID string `json:"model_id"`
}

// POST /api/v1/models/switch
func (h *Handler) SwitchModel(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	var req SwitchModelRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid payload")
		return
	}

	if err := h.engine.SetActiveModel(req.ModelID); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":        "updated",
		"current_model": h.engine.GetActiveModel(),
	})
}

// GET /api/v1/videos/{videoId}
func (h *Handler) GetVideo(w http.ResponseWriter, r *http.Request) {
	pathParts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(pathParts) < 4 {
		writeError(w, http.StatusBadRequest, "Missing videoId in path")
		return
	}
	videoId := pathParts[3]

	video, ok := h.catalog.Get(videoId)
	if !ok {
		writeError(w, http.StatusNotFound, "Video not found: "+videoId)
		return
	}

	writeJSON(w, http.StatusOK, video)
}

// GET /api/v1/compare
func (h *Handler) Compare(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		userID = "user_1001"
	}

	topK := 5
	if topKStr := r.URL.Query().Get("top_k"); topKStr != "" {
		if val, err := strconv.Atoi(topKStr); err == nil && val > 0 {
			topK = val
		}
	}

	results, err := h.engine.Compare(userID, topK)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Comparison failed: "+err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"user_id": userID,
		"top_k":   topK,
		"models":  results,
	})
}

// GET /api/v1/users
func (h *Handler) ListUsers(w http.ResponseWriter, r *http.Request) {
	users := h.engine.ListDemoUsers()
	writeJSON(w, http.StatusOK, map[string]any{
		"users": users,
	})
}

// GET /api/v1/metrics/offline
func (h *Handler) OfflineMetrics(w http.ResponseWriter, r *http.Request) {
	summaryPath := filepath.Join(h.dataDir, "metrics_summary.json")
	bytes, err := os.ReadFile(summaryPath)
	if err != nil {
		writeError(w, http.StatusNotFound, "Offline metrics file not found")
		return
	}

	var data any
	if err := json.Unmarshal(bytes, &data); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to parse offline metrics")
		return
	}

	writeJSON(w, http.StatusOK, data)
}
