package database

import (
	"context"
	"testing"
)

func TestMemoryStorePersistsFeedbackAndRecommendations(t *testing.T) {
	db, err := Open(":memory:")
	if err != nil { t.Fatal(err) }
	defer db.Close()
	ctx := context.Background()
	if err := db.LogFeedback(ctx, "u1", "v1", "play", "hybrid"); err != nil { t.Fatal(err) }
	if err := db.LogFeedback(ctx, "u1", "v2", "skip", "hybrid"); err != nil { t.Fatal(err) }
	if err := db.LogRecommendation(ctx, "request-1", "u1", "hybrid", 5, false); err != nil { t.Fatal(err) }
	counts, err := db.GetFeedbackSummary(ctx)
	if err != nil { t.Fatal(err) }
	if counts["play"] != 1 || counts["skip"] != 1 { t.Fatalf("unexpected feedback counts: %#v", counts) }
	if len(db.recommendations) != 1 { t.Fatalf("expected one recommendation log, got %d", len(db.recommendations)) }
}
