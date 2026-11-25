package recommender_test

import (
	"path/filepath"
	"testing"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
)

func setupTestEngine(t *testing.T) (*recommender.Engine, *catalog.Repository) {
	t.Helper()
	dataDir := filepath.Join("..", "..", "testdata")
	catRepo, err := catalog.NewRepository(filepath.Join(dataDir, "catalog.json"))
	if err != nil {
		t.Fatalf("failed to load test catalog: %v", err)
	}

	engine, err := recommender.NewEngine(dataDir, catRepo)
	if err != nil {
		t.Fatalf("failed to init recommender engine: %v", err)
	}
	return engine, catRepo
}

func TestRecommender_KnownUser(t *testing.T) {
	engine, _ := setupTestEngine(t)

	resp, err := engine.Recommend(recommender.RecommendationRequest{
		UserID:      "user_1001",
		TopK:        5,
		ExcludeSeen: true,
	})
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if resp.Fallback {
		t.Errorf("expected fallback=false for known user, got true")
	}

	if len(resp.Recommendations) != 5 {
		t.Errorf("expected 5 recommendations, got %d", len(resp.Recommendations))
	}

	for _, item := range resp.Recommendations {
		if item.Score < 0 || item.Score > 1.0 {
			t.Errorf("score out of range [0, 1]: %f", item.Score)
		}
		if len(item.Reasons) == 0 {
			t.Errorf("item %s has empty reasons", item.ItemID)
		}
	}
}

func TestRecommender_ColdStartUser(t *testing.T) {
	engine, _ := setupTestEngine(t)

	resp, err := engine.Recommend(recommender.RecommendationRequest{
		UserID:      "user_cold_start",
		TopK:        10,
		ExcludeSeen: true,
	})
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	if !resp.Fallback {
		t.Errorf("expected fallback=true for cold-start user")
	}

	if resp.Model != "popularity-positive-event-count-v1" {
		t.Errorf("expected model popularity-positive-event-count-v1 for cold start, got %s", resp.Model)
	}

	for _, item := range resp.Recommendations {
		if len(item.Reasons) == 0 || item.Reasons[0].Code != "cold_start" {
			t.Errorf("expected reason cold_start, got %v", item.Reasons)
		}
	}
}

func TestRecommender_ExcludeSeenItems(t *testing.T) {
	engine, _ := setupTestEngine(t)

	history := engine.GetUserHistory("user_1001")
	seen := make(map[string]bool)
	for _, h := range history {
		seen[h.ItemID] = true
	}

	resp, err := engine.Recommend(recommender.RecommendationRequest{
		UserID:      "user_1001",
		TopK:        10,
		ExcludeSeen: true,
	})
	if err != nil {
		t.Fatalf("recommend error: %v", err)
	}

	for _, item := range resp.Recommendations {
		if seen[item.ItemID] {
			t.Errorf("already seen item %s was recommended when ExcludeSeen=true", item.ItemID)
		}
	}
	if len(history) > 0 {
		// Saved offline predictions must still honor a runtime candidate filter
		// and never return the requested item if it is in the user's history.
		filtered, err := engine.Recommend(recommender.RecommendationRequest{
			UserID: "user_1001", TopK: 5, ExcludeSeen: true,
			CandidateIDs: []string{history[0].ItemID},
		})
		if err != nil { t.Fatalf("filtered recommendation failed: %v", err) }
		if len(filtered.Recommendations) != 0 { t.Fatalf("expected no results for an already-seen-only candidate set, got %d", len(filtered.Recommendations)) }
	}
}

func TestRecommender_ModelSwitching(t *testing.T) {
	engine, _ := setupTestEngine(t)

	err := engine.SetActiveModel("item-cf-cosine-v1")
	if err != nil {
		t.Fatalf("failed to switch model to item-cf-cosine-v1: %v", err)
	}

	if engine.GetActiveModel() != "item-cf-cosine-v1" {
		t.Errorf("expected active model item-cf-cosine-v1, got %s", engine.GetActiveModel())
	}

	err = engine.SetActiveModel("non_existent_model")
	if err == nil {
		t.Errorf("expected error for non-existent model, got nil")
	}
}

func TestCompareDoesNotChangeActiveModel(t *testing.T) {
	engine, _ := setupTestEngine(t)
	before := engine.GetActiveModel()
	if _, err := engine.Compare("user_1001", 3); err != nil { t.Fatal(err) }
	if got := engine.GetActiveModel(); got != before { t.Fatalf("Compare changed active model from %q to %q", before, got) }
}
