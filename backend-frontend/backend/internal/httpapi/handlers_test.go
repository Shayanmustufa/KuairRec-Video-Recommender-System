package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

const fixture = "../../testdata"

type testServer struct {
	handler *Handler
	router  http.Handler
	db      *database.DB
}

func newServer(t *testing.T, opts RouterOptions, adminToken string) *testServer {
	t.Helper()
	repo, err := catalog.NewRepository(filepath.Join(fixture, "catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	engine, err := recommender.NewEngine(fixture, repo)
	if err != nil {
		t.Fatal(err)
	}
	db, err := database.Open(context.Background(), ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	h, err := NewHandler(engine, repo, db, Options{DataDir: fixture, AdminToken: adminToken, LogRequestsToDB: true})
	if err != nil {
		t.Fatal(err)
	}
	if opts.AllowedOrigins == nil {
		opts.AllowedOrigins = []string{"http://localhost:3000"}
	}
	return &testServer{handler: h, router: NewRouter(h, opts), db: db}
}

func (s *testServer) do(t *testing.T, method, path string, body any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	var reader *bytes.Reader
	switch b := body.(type) {
	case nil:
		reader = bytes.NewReader(nil)
	case string:
		reader = bytes.NewReader([]byte(b))
	default:
		raw, _ := json.Marshal(b)
		reader = bytes.NewReader(raw)
	}
	req := httptest.NewRequest(method, path, reader)
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	s.router.ServeHTTP(rec, req)
	s.handler.Wait()
	return rec
}

func decode(t *testing.T, rec *httptest.ResponseRecorder, into any) {
	t.Helper()
	if err := json.Unmarshal(rec.Body.Bytes(), into); err != nil {
		t.Fatalf("invalid JSON (%d): %s", rec.Code, rec.Body.String())
	}
}

func TestHealthReadyAndMetrics(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	if rec := s.do(t, http.MethodGet, "/healthz", nil, nil); rec.Code != http.StatusOK {
		t.Fatalf("healthz %d", rec.Code)
	}
	rec := s.do(t, http.MethodGet, "/readyz", nil, nil)
	var ready map[string]any
	decode(t, rec, &ready)
	if rec.Code != http.StatusOK || ready["status"] != "ready" || ready["known_users"].(float64) != 3 {
		t.Fatalf("readyz %d %v", rec.Code, ready)
	}
	if rec.Header().Get(telemetry.HeaderRequestID) == "" {
		t.Fatal("missing X-Request-ID")
	}
	if _, err := strconv.ParseFloat(rec.Header().Get(telemetry.HeaderResponseTime), 64); err != nil {
		t.Fatalf("X-Response-Time-Ms not numeric: %q", rec.Header().Get(telemetry.HeaderResponseTime))
	}
	rec = s.do(t, http.MethodGet, "/metrics", nil, nil)
	var metrics map[string]any
	decode(t, rec, &metrics)
	if metrics["total_requests"].(float64) < 2 || metrics["feedback_by_action"] == nil {
		t.Fatalf("metrics: %v", metrics)
	}
}

func TestRecommendKnownUserAndLogsRequestID(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	rec := s.do(t, http.MethodPost, "/api/v1/recommendations",
		map[string]any{"user_id": "1", "top_k": 2, "exclude_seen": true, "candidate_ids": nil},
		map[string]string{telemetry.HeaderRequestID: "trace-abc"})
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	var resp recommender.RecommendationResponse
	decode(t, rec, &resp)
	if resp.TopK != 2 || resp.Fallback || resp.Recommendations[0].Reasons[0].Evidence == nil || resp.GeneratedAt == "" {
		t.Fatalf("unexpected response: %+v", resp)
	}
	if rec.Header().Get(telemetry.HeaderRequestID) != "trace-abc" {
		t.Fatal("client request ID not echoed")
	}
	logs, _ := s.db.ListRecommendations(context.Background(), database.Filter{RequestID: "trace-abc"})
	if len(logs) != 1 || logs[0].UserStatus != "known" || len(logs[0].ItemIDs) != 2 {
		t.Fatalf("recommendation log not stored with request ID: %+v", logs)
	}
	rec = s.do(t, http.MethodGet, "/api/v1/logs/requests?request_id=trace-abc", nil, nil)
	var reqLogs struct {
		Requests []database.APIRequest `json:"requests"`
	}
	decode(t, rec, &reqLogs)
	if len(reqLogs.Requests) != 1 || reqLogs.Requests[0].Status != 200 || reqLogs.Requests[0].Path != "/api/v1/recommendations" {
		t.Fatalf("API request log not queryable: %+v", reqLogs)
	}
}

func TestRecommendValidation(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	cases := []struct {
		name string
		body any
		code int
	}{
		{"missing user", map[string]any{"top_k": 5}, 400},
		{"bad user chars", map[string]any{"user_id": "a b"}, 400},
		{"top_k too large", map[string]any{"user_id": "1", "top_k": 21}, 400},
		{"negative top_k", map[string]any{"user_id": "1", "top_k": -3}, 400},
		{"unknown field", map[string]any{"user_id": "1", "topk": 5}, 400},
		{"malformed", `{"user_id":`, 400},
		{"two objects", `{"user_id":"1"}{"user_id":"2"}`, 400},
		{"unknown candidate", map[string]any{"user_id": "1", "candidate_ids": []string{"999"}}, 400},
		{"unknown model", map[string]any{"user_id": "1", "model": "gpt"}, 400},
		{"model not exported for user", map[string]any{"user_id": "3", "model": "item-cf-cosine-v1"}, 404},
		{"unknown user falls back", map[string]any{"user_id": "stranger"}, 200},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if rec := s.do(t, http.MethodPost, "/api/v1/recommendations", tc.body, nil); rec.Code != tc.code {
				t.Fatalf("got %d want %d: %s", rec.Code, tc.code, rec.Body)
			}
		})
	}
	if rec := s.do(t, http.MethodGet, "/api/v1/recommendations", nil, nil); rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("GET recommendations: %d", rec.Code)
	}
}

func TestUnknownUserResponseIsExplicit(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	rec := s.do(t, http.MethodPost, "/api/v1/recommendations", map[string]any{"user_id": "stranger", "top_k": 3}, nil)
	var resp recommender.RecommendationResponse
	decode(t, rec, &resp)
	if !resp.Fallback || resp.UserStatus != "unknown" || resp.FallbackReason != "unknown_user" || resp.Recommendations[0].Reasons[0].Code != "cold_start" {
		t.Fatalf("unexpected: %+v", resp)
	}
	if rec := s.do(t, http.MethodGet, "/api/v1/users/stranger", nil, nil); rec.Code != http.StatusNotFound {
		t.Fatalf("user detail for unknown user: %d", rec.Code)
	}
	if rec := s.do(t, http.MethodGet, "/api/v1/users/1", nil, nil); rec.Code != http.StatusOK {
		t.Fatalf("user detail for known user: %d", rec.Code)
	}
}

func TestFeedbackLifecycle(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	rec := s.do(t, http.MethodPost, "/api/v1/feedback", map[string]any{"user_id": "1", "item_id": "3", "action": "play", "rank": 1}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("feedback: %d %s", rec.Code, rec.Body)
	}
	bad := []map[string]any{
		{"user_id": "1", "item_id": "3", "action": "like"},
		{"user_id": "1", "item_id": "999", "action": "play"},
		{"user_id": "", "item_id": "3", "action": "play"},
		{"user_id": "1", "item_id": "3", "action": "play", "model_id": "nope"},
		{"user_id": "1", "item_id": "3", "action": "play", "rank": 0},
	}
	for _, body := range bad {
		if rec := s.do(t, http.MethodPost, "/api/v1/feedback", body, nil); rec.Code != http.StatusBadRequest {
			t.Fatalf("%v: got %d", body, rec.Code)
		}
	}
	rec = s.do(t, http.MethodGet, "/api/v1/feedback?user_id=1", nil, nil)
	var list struct {
		Events  []database.FeedbackEvent `json:"events"`
		Summary map[string]int           `json:"summary"`
	}
	decode(t, rec, &list)
	if len(list.Events) != 1 || list.Events[0].ModelID != "hybrid-validation-selected-v1" || list.Summary["play"] != 1 {
		t.Fatalf("unexpected feedback list: %+v", list)
	}
}

func TestCompareAndModels(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	rec := s.do(t, http.MethodGet, "/api/v1/compare?user_id=1&top_k=3", nil, nil)
	var cmp recommender.CompareResult
	decode(t, rec, &cmp)
	if rec.Code != 200 || len(cmp.Models) != 4 {
		t.Fatalf("compare: %d %+v", rec.Code, cmp)
	}
	for path, code := range map[string]int{
		"/api/v1/compare":                   400,
		"/api/v1/compare?user_id=1&top_k=0": 400,
		"/api/v1/compare?user_id=3":         404,
		"/api/v1/compare?user_id=1&top_k=x": 400,
		"/api/v1/models":                    200,
		"/api/v1/models/current":            200,
		"/api/v1/users":                     200,
		"/api/v1/metrics/offline":           200,
		"/api/v1/videos/3":                  200,
		"/api/v1/videos/999":                404,
		"/api/v1/videos/1/similar?top_k=2":  200,
		"/api/v1/videos/1/similar?top_k=99": 400,
		"/api/v1/videos/999/similar":        404,
		"/api/v1/logs/recommendations":      200,
		"/api/v1/logs/requests?limit=0":     400,
		"/api/v1/does-not-exist":            404,
	} {
		if rec := s.do(t, http.MethodGet, path, nil, nil); rec.Code != code {
			t.Errorf("%s: got %d want %d (%s)", path, rec.Code, code, rec.Body)
		}
	}
}

func TestSwitchModelAdminToken(t *testing.T) {
	s := newServer(t, RouterOptions{}, "secret")
	body := map[string]any{"model_id": "item-cf-cosine-v1"}
	if rec := s.do(t, http.MethodPost, "/api/v1/models/switch", body, nil); rec.Code != http.StatusUnauthorized {
		t.Fatalf("switch without token: %d", rec.Code)
	}
	if rec := s.do(t, http.MethodPost, "/api/v1/models/switch", map[string]any{"model_id": "x"}, map[string]string{"X-Admin-Token": "secret"}); rec.Code != http.StatusBadRequest {
		t.Fatalf("switch to unknown model: %d", rec.Code)
	}
	if rec := s.do(t, http.MethodPost, "/api/v1/models/switch", body, map[string]string{"X-Admin-Token": "secret"}); rec.Code != http.StatusOK {
		t.Fatalf("switch with token: %d", rec.Code)
	}
}

func TestCORS(t *testing.T) {
	s := newServer(t, RouterOptions{}, "")
	rec := s.do(t, http.MethodOptions, "/api/v1/recommendations", nil, map[string]string{
		"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
	if rec.Header().Get("Access-Control-Allow-Origin") != "http://localhost:3000" {
		t.Fatalf("allowed origin not echoed: %v", rec.Header())
	}
	rec = s.do(t, http.MethodGet, "/api/v1/models", nil, map[string]string{"Origin": "http://evil.example"})
	if rec.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatal("disallowed origin must not receive CORS headers")
	}
}

func TestRateLimit(t *testing.T) {
	s := newServer(t, RouterOptions{RateLimitPerMinute: 3}, "")
	codes := []int{}
	for i := 0; i < 4; i++ {
		codes = append(codes, s.do(t, http.MethodGet, "/api/v1/models", nil, nil).Code)
	}
	if codes[2] != 200 || codes[3] != http.StatusTooManyRequests {
		t.Fatalf("rate limit not enforced: %v", codes)
	}
	if rec := s.do(t, http.MethodGet, "/healthz", nil, nil); rec.Code != 200 {
		t.Fatal("health probes must not be rate limited")
	}
}
