package httpapi_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/httpapi"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
)

func setupTestRouter(t *testing.T) http.Handler {
	t.Helper()
	dataDir := filepath.Join("..", "..", "testdata")
	catRepo, err := catalog.NewRepository(filepath.Join(dataDir, "catalog.json"))
	if err != nil {
		t.Fatalf("catalog error: %v", err)
	}

	engine, err := recommender.NewEngine(dataDir, catRepo)
	if err != nil {
		t.Fatalf("recommender error: %v", err)
	}

	db, _ := database.Open(":memory:")
	h := httpapi.NewHandler(engine, catRepo, db, dataDir)
	return httpapi.NewRouter(h, []string{"*"})
}

func TestHealthAndReadyEndpoints(t *testing.T) {
	router := setupTestRouter(t)

	// Healthz
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200 on /healthz, got %d", rr.Code)
	}

	// Readyz
	req = httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rr = httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200 on /readyz, got %d", rr.Code)
	}
}

func TestRecommendEndpoint(t *testing.T) {
	router := setupTestRouter(t)

	payload := map[string]any{
		"user_id":      "user_1001",
		"top_k":        5,
		"exclude_seen": true,
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/recommendations", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200 on recommendation endpoint, got %d. Body: %s", rr.Code, rr.Body.String())
	}

	var resp recommender.RecommendationResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.UserID != "user_1001" {
		t.Errorf("expected user_id user_1001, got %s", resp.UserID)
	}
	if len(resp.Recommendations) != 5 {
		t.Errorf("expected 5 items, got %d", len(resp.Recommendations))
	}
}

func TestFeedbackEndpoint(t *testing.T) {
	router := setupTestRouter(t)

	payload := map[string]string{
		"user_id":  "user_1001",
		"item_id":  "v_105",
		"action":   "click",
		"model_id": "hybrid-validation-selected-v1",
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/feedback", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200 on feedback endpoint, got %d", rr.Code)
	}
}

func TestSimilarVideosEndpoint(t *testing.T) {
	router := setupTestRouter(t)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/videos/v_101/similar?top_k=3", nil)
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK { t.Fatalf("expected 200, got %d: %s", rr.Code, rr.Body.String()) }
	var payload struct { SimilarItems []struct { ItemID string `json:"item_id"`; Score float64 `json:"score"` } `json:"similar_items"` }
	if err := json.Unmarshal(rr.Body.Bytes(), &payload); err != nil { t.Fatal(err) }
	if len(payload.SimilarItems) > 3 { t.Fatalf("expected at most 3 neighbors, got %d", len(payload.SimilarItems)) }
}

func TestCompareRejectsMissingUser(t *testing.T) {
	router := setupTestRouter(t)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/compare", nil)
	rr := httptest.NewRecorder()
	router.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest { t.Fatalf("expected 400, got %d", rr.Code) }
}
