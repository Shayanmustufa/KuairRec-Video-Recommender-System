package recommender

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/explanation"
)

const fixture = "../../testdata"

func newEngine(t *testing.T, dir string) *Engine {
	t.Helper()
	repo, err := catalog.NewRepository(filepath.Join(dir, "catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	engine, err := NewEngine(dir, repo)
	if err != nil {
		t.Fatal(err)
	}
	return engine
}

func boolPtr(v bool) *bool { return &v }

func TestKnownUserServesFrozenSelectedList(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "1", TopK: 3})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Fallback || resp.UserStatus != explanation.UserKnown || resp.Model != "hybrid-validation-selected-v1" || resp.ArtifactSplit != "test" {
		t.Fatalf("unexpected response header fields: %+v", resp)
	}
	want := []string{"3", "1", "4"}
	for i, item := range resp.Recommendations {
		if item.ItemID != want[i] || item.Rank != i+1 {
			t.Fatalf("rank %d: got %s/%d, want %s", i+1, item.ItemID, item.Rank, want[i])
		}
		if item.Video == nil || len(item.Reasons) == 0 || item.Components["item_cf"].Weight != 0.9 {
			t.Fatalf("item %s lacks metadata, reasons or components: %+v", item.ItemID, item)
		}
	}
}

func TestUnknownUserGetsLabelledFallback(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "does-not-exist", TopK: 3})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Fallback || resp.UserStatus != explanation.UserUnknown || resp.FallbackReason != "unknown_user" ||
		resp.Model != "popularity-positive-event-count-v1" {
		t.Fatalf("unexpected fallback response: %+v", resp)
	}
	if got := resp.Recommendations[0]; got.ItemID != "1" || got.Reasons[0].Code != explanation.CodeColdStart ||
		got.Reasons[0].Evidence["positive_training_event_count"] != 50 {
		t.Fatalf("fallback must follow frozen popularity order with evidence: %+v", got)
	}
}

func TestNoHistoryUserFallsBackAndExcludesSeen(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "2", TopK: 2})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Fallback || resp.UserStatus != explanation.UserNoHistory || resp.FallbackReason != "no_positive_history" {
		t.Fatalf("unexpected response: %+v", resp)
	}
	if resp.Recommendations[0].ItemID != "2" { // item 1 is in user 2's seen history
		t.Fatalf("seen item was not excluded: %+v", resp.Recommendations)
	}
	resp, _ = e.Recommend(RecommendationRequest{UserID: "2", TopK: 2, ExcludeSeen: boolPtr(false)})
	if resp.Recommendations[0].ItemID != "1" || resp.ExcludeSeen {
		t.Fatalf("exclude_seen=false should keep seen items: %+v", resp.Recommendations)
	}
}

func TestForcedColdStartForKnownUser(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "1", TopK: 5, ForceColdStart: true})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Fallback || resp.FallbackReason != "cold_start_requested" || resp.UserStatus != explanation.UserKnown {
		t.Fatalf("unexpected response: %+v", resp)
	}
	for _, item := range resp.Recommendations {
		if item.ItemID == "5" || item.ItemID == "7" {
			t.Fatalf("seen item %s returned", item.ItemID)
		}
		if item.Reasons[0].Evidence["forced"] != true {
			t.Fatalf("forced flag missing from evidence: %+v", item.Reasons[0])
		}
	}
}

func TestCandidateFilterAndValidation(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "1", TopK: 10, CandidateIDs: []string{"4", "1"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Recommendations) != 2 || resp.Recommendations[0].ItemID != "1" || resp.Recommendations[1].Rank != 2 {
		t.Fatalf("candidate filter not applied or ranks not reassigned: %+v", resp.Recommendations)
	}
	_, err = e.Recommend(RecommendationRequest{UserID: "1", CandidateIDs: []string{"1", "999"}})
	var unknown *UnknownItemsError
	if !errors.As(err, &unknown) || len(unknown.IDs) != 1 || unknown.IDs[0] != "999" {
		t.Fatalf("expected UnknownItemsError for 999, got %v", err)
	}
}

func TestTopKBounds(t *testing.T) {
	e := newEngine(t, fixture)
	for _, k := range []int{-1, MaxTopK + 1} {
		if _, err := e.Recommend(RecommendationRequest{UserID: "1", TopK: k}); !errors.Is(err, ErrInvalidTopK) {
			t.Fatalf("top_k=%d: expected ErrInvalidTopK, got %v", k, err)
		}
	}
	resp, err := e.Recommend(RecommendationRequest{UserID: "1"})
	if err != nil || resp.TopK != 4 { // default 10, fixture list has 4 items
		t.Fatalf("default top_k: %v %+v", err, resp)
	}
}

func TestPerRequestModelDoesNotChangeDefault(t *testing.T) {
	e := newEngine(t, fixture)
	resp, err := e.Recommend(RecommendationRequest{UserID: "1", Model: "item-cf-cosine-v1"})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Model != "item-cf-cosine-v1" || resp.ArtifactSplit != "validation" || resp.Recommendations[0].ItemID != "4" {
		t.Fatalf("unexpected per-request model response: %+v", resp)
	}
	if e.DefaultModel() != "hybrid-validation-selected-v1" {
		t.Fatalf("per-request model changed the default: %s", e.DefaultModel())
	}
	if _, err := e.Recommend(RecommendationRequest{UserID: "1", Model: "nope"}); !errors.Is(err, ErrUnknownModel) {
		t.Fatalf("expected ErrUnknownModel, got %v", err)
	}
	if _, err := e.Recommend(RecommendationRequest{UserID: "3", Model: "item-cf-cosine-v1"}); !errors.Is(err, ErrModelNotServable) {
		t.Fatalf("non-demo user with comparison model: expected ErrModelNotServable, got %v", err)
	}
}

func TestSetDefaultModel(t *testing.T) {
	e := newEngine(t, fixture)
	if err := e.SetDefaultModel("unknown"); !errors.Is(err, ErrUnknownModel) {
		t.Fatalf("expected ErrUnknownModel, got %v", err)
	}
	if err := e.SetDefaultModel("popularity-positive-event-count-v1"); err != nil {
		t.Fatal(err)
	}
	resp, _ := e.Recommend(RecommendationRequest{UserID: "1"})
	if resp.Model != "popularity-positive-event-count-v1" {
		t.Fatalf("default model not applied: %s", resp.Model)
	}
}

func TestCompareUsesSameSplitForAllModels(t *testing.T) {
	e := newEngine(t, fixture)
	result, err := e.Compare("1", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Models) != 4 || result.ArtifactSplit != "validation" {
		t.Fatalf("unexpected compare result: %+v", result)
	}
	if result.Models["hybrid-validation-selected-v1"].Recommendations[0].ItemID != "3" {
		t.Fatalf("hybrid comparison column wrong: %+v", result.Models["hybrid-validation-selected-v1"])
	}
	if _, err := e.Compare("3", 5); !errors.Is(err, ErrNoComparisonExport) {
		t.Fatalf("expected ErrNoComparisonExport, got %v", err)
	}
	empty, _ := e.Compare("2", 5)
	if col := empty.Models["item-cf-cosine-v1"]; len(col.Recommendations) != 0 || col.EmptyReason == "" {
		t.Fatalf("empty column should explain itself: %+v", col)
	}
}

func TestSimilarItemsOrdered(t *testing.T) {
	e := newEngine(t, fixture)
	items := e.SimilarItems("1", 2)
	if len(items) != 2 || items[0].ItemID != "3" || items[1].ItemID != "4" {
		t.Fatalf("unexpected neighbors: %+v", items)
	}
}

func TestUserDetailAndDemoUsers(t *testing.T) {
	e := newEngine(t, fixture)
	if _, ok := e.User("nobody"); ok {
		t.Fatal("unknown user must not have a profile")
	}
	detail, ok := e.User("1")
	if !ok || detail.Status != explanation.UserKnown || len(detail.RecentPositive) != 1 || detail.RecentPositive[0].Video == nil {
		t.Fatalf("unexpected detail: %+v", detail)
	}
	users := e.DemoUsers()
	if len(users) != 2 || users[0].UserID != "1" || users[1].Status != explanation.UserNoHistory {
		t.Fatalf("unexpected demo users: %+v", users)
	}
}

// copyFixture copies the fixture so a test can corrupt it.
func copyFixture(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	entries, err := os.ReadDir(fixture)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range entries {
		raw, err := os.ReadFile(filepath.Join(fixture, entry.Name()))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, entry.Name()), raw, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func editJSON(t *testing.T, path string, edit func(map[string]any)) {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	edit(doc)
	raw, _ = json.Marshal(doc)
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestStartupRejectsReasonWithoutEvidence(t *testing.T) {
	dir := copyFixture(t)
	editJSON(t, filepath.Join(dir, "recommendations.json"), func(doc map[string]any) {
		item := doc["1"].([]any)[0].(map[string]any)
		reason := item["reasons"].([]any)[0].(map[string]any)
		delete(reason["evidence"].(map[string]any), "similarity")
	})
	repo, _ := catalog.NewRepository(filepath.Join(dir, "catalog.json"))
	if _, err := NewEngine(dir, repo); err == nil {
		t.Fatal("expected startup failure for reason missing evidence")
	}
}

func TestStartupRejectsDisabledCodeForSelectedModel(t *testing.T) {
	dir := copyFixture(t)
	editJSON(t, filepath.Join(dir, "recommendations.json"), func(doc map[string]any) {
		item := doc["1"].([]any)[0].(map[string]any)
		item["reasons"] = []any{map[string]any{"code": "extension_model_match", "text": "x",
			"evidence": map[string]any{"lightgcn_score": 1, "lightgcn_weight": 0}}}
	})
	repo, _ := catalog.NewRepository(filepath.Join(dir, "catalog.json"))
	if _, err := NewEngine(dir, repo); err == nil {
		t.Fatal("expected startup failure for disabled reason code in selected list")
	}
}

func TestStartupVerifiesBundleChecksums(t *testing.T) {
	dir := copyFixture(t)
	editJSON(t, filepath.Join(dir, "model_manifest.json"), func(doc map[string]any) {
		doc["bundle_sha256"] = map[string]any{"popularity.json": "0000"}
	})
	repo, _ := catalog.NewRepository(filepath.Join(dir, "catalog.json"))
	if _, err := NewEngine(dir, repo); !errors.Is(err, errBundleChecksumFails) {
		t.Fatalf("expected checksum failure, got %v", err)
	}
}

func TestStartupRejectsBadWeights(t *testing.T) {
	dir := copyFixture(t)
	editJSON(t, filepath.Join(dir, "model_manifest.json"), func(doc map[string]any) {
		doc["selected_weights"] = map[string]any{"popularity": 0.5, "item_cf": 0.9, "lightgcn": 0}
	})
	repo, _ := catalog.NewRepository(filepath.Join(dir, "catalog.json"))
	if _, err := NewEngine(dir, repo); err == nil {
		t.Fatal("expected failure when weights do not sum to 1")
	}
}

// TestProductionServingBundle loads the real checked-in bundle, verifying its
// checksums and that every served reason carries the required evidence.
func TestProductionServingBundle(t *testing.T) {
	dir := "../../serving_data"
	if _, err := os.Stat(filepath.Join(dir, "model_manifest.json")); err != nil {
		t.Skip("serving bundle not present")
	}
	e := newEngine(t, dir)
	if !e.Manifest().BundleVerifiedAtLoad {
		t.Fatal("production bundle must carry checksums")
	}
	if e.UserCount() != 7176 || len(e.DemoUsers()) != 100 {
		t.Fatalf("unexpected bundle size: users=%d demo=%d", e.UserCount(), len(e.DemoUsers()))
	}
	resp, err := e.Recommend(RecommendationRequest{UserID: "0", TopK: 10})
	if err != nil || resp.Fallback || len(resp.Recommendations) != 10 {
		t.Fatalf("known user 0: %v %+v", err, resp)
	}
	for _, id := range []string{"735", "2197", "4427", "4445"} { // no positive pre-test history
		resp, err := e.Recommend(RecommendationRequest{UserID: id, TopK: 5})
		if err != nil || !resp.Fallback || resp.UserStatus != explanation.UserNoHistory {
			t.Fatalf("user %s should use no-history fallback: %v %+v", id, err, resp)
		}
	}
}
