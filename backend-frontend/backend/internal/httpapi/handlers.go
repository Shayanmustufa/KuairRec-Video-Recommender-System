// Package httpapi exposes the REST API described in docs/API_SPEC.md.
package httpapi

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

const maxBodyBytes = 1 << 20

var validID = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,64}$`)

var allowedActions = map[string]bool{"click": true, "play": true, "skip": true, "hide": true}

// Handler holds the dependencies of every endpoint.
type Handler struct {
	engine          *recommender.Engine
	catalog         *catalog.Repository
	db              *database.DB
	metrics         *telemetry.Metrics
	offlineMetrics  json.RawMessage
	adminToken      string
	logRequestsToDB bool
	background      sync.WaitGroup
}

// Options configures a Handler.
type Options struct {
	DataDir         string
	AdminToken      string
	LogRequestsToDB bool
}

// NewHandler loads the offline metrics summary once and wires dependencies.
func NewHandler(engine *recommender.Engine, repo *catalog.Repository, db *database.DB, opts Options) (*Handler, error) {
	raw, err := os.ReadFile(filepath.Join(opts.DataDir, "metrics_summary.json"))
	if err != nil {
		return nil, fmt.Errorf("read metrics_summary.json: %w", err)
	}
	if !json.Valid(raw) {
		return nil, errors.New("metrics_summary.json is not valid JSON")
	}
	return &Handler{engine: engine, catalog: repo, db: db, metrics: telemetry.NewMetrics(),
		offlineMetrics: raw, adminToken: opts.AdminToken, logRequestsToDB: opts.LogRequestsToDB}, nil
}

// Wait blocks until background request-log writes finish (tests, shutdown).
func (h *Handler) Wait() { h.background.Wait() }

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func decodeJSON(w http.ResponseWriter, r *http.Request, dst any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		return fmt.Errorf("invalid JSON body: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return errors.New("invalid JSON body: must contain a single object")
	}
	return nil
}

func queryInt(r *http.Request, key string, def, min, max int) (int, error) {
	value := r.URL.Query().Get(key)
	if value == "" {
		return def, nil
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed < min || parsed > max {
		return 0, fmt.Errorf("%s must be an integer from %d to %d", key, min, max)
	}
	return parsed, nil
}

// Healthz is the liveness probe.
func (h *Handler) Healthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "time": time.Now().UTC().Format(time.RFC3339)})
}

// Readyz checks the database and loaded artifacts.
func (h *Handler) Readyz(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	checks := map[string]string{"database": "ok", "catalog": "ok", "recommendations": "ok"}
	ready := true
	if err := h.db.Ping(ctx); err != nil {
		checks["database"], ready = "unavailable", false
	}
	if h.catalog.Count() == 0 {
		checks["catalog"], ready = "empty", false
	}
	if h.engine.UserCount() == 0 {
		checks["recommendations"], ready = "empty", false
	}
	status, code := "ready", http.StatusOK
	if !ready {
		status, code = "not_ready", http.StatusServiceUnavailable
	}
	writeJSON(w, code, map[string]any{
		"status": status, "checks": checks, "database_kind": h.db.Kind(),
		"catalog_items": h.catalog.Count(), "known_users": h.engine.UserCount(),
		"default_model": h.engine.DefaultModel(), "server_time": time.Now().UTC().Format(time.RFC3339),
	})
}

// Metrics returns process counters and persisted feedback totals.
func (h *Handler) Metrics(w http.ResponseWriter, r *http.Request) {
	snapshot := h.metrics.Snapshot()
	summary, err := h.db.FeedbackSummary(r.Context())
	snapshot["feedback_by_action"] = summary
	snapshot["feedback_store_available"] = err == nil
	snapshot["default_model"] = h.engine.DefaultModel()
	writeJSON(w, http.StatusOK, snapshot)
}

// Recommend handles POST /api/v1/recommendations.
func (h *Handler) Recommend(w http.ResponseWriter, r *http.Request) {
	var req recommender.RecommendationRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if !validID.MatchString(req.UserID) {
		writeError(w, http.StatusBadRequest, "user_id is required and must match [A-Za-z0-9_.-]{1,64}")
		return
	}
	if len(req.CandidateIDs) > 10000 {
		writeError(w, http.StatusBadRequest, "candidate_ids may contain at most 10000 items")
		return
	}
	resp, err := h.engine.Recommend(req)
	switch {
	case errors.Is(err, recommender.ErrInvalidTopK), errors.Is(err, recommender.ErrUnknownModel),
		errors.Is(err, recommender.ErrUnknownItems), errors.Is(err, recommender.ErrEmptyUserID):
		writeError(w, http.StatusBadRequest, err.Error())
		return
	case errors.Is(err, recommender.ErrModelNotServable):
		writeError(w, http.StatusNotFound, err.Error())
		return
	case err != nil:
		writeError(w, http.StatusInternalServerError, "recommendation failure")
		return
	}
	h.metrics.RecommendationsCount.Add(1)
	if resp.Fallback {
		h.metrics.FallbackCount.Add(1)
	}
	items := make([]string, len(resp.Recommendations))
	for i, item := range resp.Recommendations {
		items[i] = item.ItemID
	}
	logErr := h.db.LogRecommendation(r.Context(), database.RecommendationLog{
		RequestID: telemetry.RequestID(r.Context()), UserID: resp.UserID, UserStatus: string(resp.UserStatus),
		ModelID: resp.Model, TopK: resp.TopK, IsFallback: resp.Fallback, ItemIDs: items, LatencyMs: resp.LatencyMs,
	})
	if logErr != nil {
		w.Header().Set("X-Recommendation-Log", "not-persisted")
	}
	writeJSON(w, http.StatusOK, resp)
}

// FeedbackRequest is the POST /api/v1/feedback body.
type FeedbackRequest struct {
	UserID  string `json:"user_id"`
	ItemID  string `json:"item_id"`
	Action  string `json:"action"`
	ModelID string `json:"model_id"`
	Rank    *int   `json:"rank,omitempty"`
}

// CreateFeedback records a click/play/skip/hide on a displayed item. It is
// stored for analysis only; it does not retrain any model.
func (h *Handler) CreateFeedback(w http.ResponseWriter, r *http.Request) {
	var req FeedbackRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	switch {
	case !validID.MatchString(req.UserID):
		writeError(w, http.StatusBadRequest, "user_id is required and must match [A-Za-z0-9_.-]{1,64}")
		return
	case !allowedActions[req.Action]:
		writeError(w, http.StatusBadRequest, "action must be one of click, play, skip, hide")
		return
	case !h.catalog.Has(req.ItemID):
		writeError(w, http.StatusBadRequest, "item_id is not in the eligible catalog")
		return
	case req.Rank != nil && (*req.Rank < 1 || *req.Rank > recommender.MaxTopK):
		writeError(w, http.StatusBadRequest, fmt.Sprintf("rank must be from 1 to %d", recommender.MaxTopK))
		return
	}
	if req.ModelID == "" {
		req.ModelID = h.engine.DefaultModel()
	}
	if !h.engine.HasModel(req.ModelID) {
		writeError(w, http.StatusBadRequest, "model_id is not registered in the manifest")
		return
	}
	event, err := h.db.LogFeedback(r.Context(), database.FeedbackEvent{
		RequestID: telemetry.RequestID(r.Context()), UserID: req.UserID, ItemID: req.ItemID,
		Action: req.Action, ModelID: req.ModelID, Rank: req.Rank,
	})
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "feedback store unavailable")
		return
	}
	h.metrics.FeedbackCount.Add(1)
	writeJSON(w, http.StatusCreated, map[string]any{"status": "recorded", "event": event,
		"note": "Feedback is stored for analysis; the frozen models are not retrained online."})
}

// ListFeedback handles GET /api/v1/feedback?user_id=&limit=.
func (h *Handler) ListFeedback(w http.ResponseWriter, r *http.Request) {
	limit, err := queryInt(r, "limit", 50, 1, 500)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	events, err := h.db.ListFeedback(r.Context(), database.Filter{UserID: r.URL.Query().Get("user_id"), Limit: limit})
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "feedback store unavailable")
		return
	}
	summary, _ := h.db.FeedbackSummary(r.Context())
	writeJSON(w, http.StatusOK, map[string]any{"events": events, "summary": summary})
}

// ListModels handles GET /api/v1/models.
func (h *Handler) ListModels(w http.ResponseWriter, r *http.Request) {
	m := h.engine.Manifest()
	writeJSON(w, http.StatusOK, map[string]any{"models": m.Models, "current_model": m.CurrentModel,
		"default_model": m.ActiveDefaultModel, "fallback_model": m.FallbackModel})
}

// CurrentModel handles GET /api/v1/models/current (full manifest).
func (h *Handler) CurrentModel(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, h.engine.Manifest())
}

// SwitchModel changes the server-wide default model (admin operation). When
// ADMIN_TOKEN is configured the X-Admin-Token header must match. The UI uses
// the per-request "model" field instead, so browsers never change shared state.
func (h *Handler) SwitchModel(w http.ResponseWriter, r *http.Request) {
	if h.adminToken != "" && subtle.ConstantTimeCompare([]byte(r.Header.Get("X-Admin-Token")), []byte(h.adminToken)) != 1 {
		writeError(w, http.StatusUnauthorized, "admin token required")
		return
	}
	var req struct {
		ModelID string `json:"model_id"`
	}
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.engine.SetDefaultModel(req.ModelID); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "updated", "default_model": h.engine.DefaultModel()})
}

// Compare handles GET /api/v1/compare?user_id=&top_k=.
func (h *Handler) Compare(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if !validID.MatchString(userID) {
		writeError(w, http.StatusBadRequest, "user_id query parameter is required")
		return
	}
	topK, err := queryInt(r, "top_k", 5, 1, recommender.MaxTopK)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	result, err := h.engine.Compare(userID, topK)
	if errors.Is(err, recommender.ErrNoComparisonExport) {
		writeError(w, http.StatusNotFound, err.Error()+" (use a user from GET /api/v1/users)")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "comparison failure")
		return
	}
	writeJSON(w, http.StatusOK, result)
}

// ListUsers handles GET /api/v1/users.
func (h *Handler) ListUsers(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"users": h.engine.DemoUsers(), "known_users_total": h.engine.UserCount()})
}

// GetUser handles GET /api/v1/users/{userID}.
func (h *Handler) GetUser(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	if !validID.MatchString(userID) {
		writeError(w, http.StatusBadRequest, "invalid user id")
		return
	}
	detail, ok := h.engine.User(userID)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "unknown user", "user_status": "unknown"})
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

// GetVideo handles GET /api/v1/videos/{videoID}.
func (h *Handler) GetVideo(w http.ResponseWriter, r *http.Request) {
	video, ok := h.catalog.Get(chi.URLParam(r, "videoID"))
	if !ok {
		writeError(w, http.StatusNotFound, "video not found in the eligible catalog")
		return
	}
	writeJSON(w, http.StatusOK, video)
}

// GetSimilarVideos handles GET /api/v1/videos/{videoID}/similar?top_k=.
func (h *Handler) GetSimilarVideos(w http.ResponseWriter, r *http.Request) {
	videoID := chi.URLParam(r, "videoID")
	if !h.catalog.Has(videoID) {
		writeError(w, http.StatusNotFound, "video not found in the eligible catalog")
		return
	}
	topK, err := queryInt(r, "top_k", 5, 1, 20)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"item_id": videoID, "similarity": "frozen Item-CF cosine (train only)",
		"similar_items": h.engine.SimilarItems(videoID, topK)})
}

// OfflineMetrics handles GET /api/v1/metrics/offline.
func (h *Handler) OfflineMetrics(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	_, _ = w.Write(h.offlineMetrics)
}

// ListRequestLogs handles GET /api/v1/logs/requests?request_id=&limit=.
func (h *Handler) ListRequestLogs(w http.ResponseWriter, r *http.Request) {
	limit, err := queryInt(r, "limit", 50, 1, 500)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	rows, err := h.db.ListAPIRequests(r.Context(), database.Filter{RequestID: r.URL.Query().Get("request_id"), Limit: limit})
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "log store unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"requests": rows})
}

// ListRecommendationLogs handles GET /api/v1/logs/recommendations?user_id=&request_id=&limit=.
func (h *Handler) ListRecommendationLogs(w http.ResponseWriter, r *http.Request) {
	limit, err := queryInt(r, "limit", 50, 1, 500)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	q := r.URL.Query()
	rows, err := h.db.ListRecommendations(r.Context(), database.Filter{UserID: q.Get("user_id"), RequestID: q.Get("request_id"), Limit: limit})
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "log store unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"recommendations": rows})
}
