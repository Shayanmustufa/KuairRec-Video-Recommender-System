package database

import (
	"context"
	"os"
	"testing"
	"time"
)

func exercise(t *testing.T, db *DB, user string) {
	t.Helper()
	ctx := context.Background()
	rank := 2
	if _, err := db.LogFeedback(ctx, FeedbackEvent{RequestID: "req-1", UserID: user, ItemID: "v1", Action: "play", ModelID: "m", Rank: &rank}); err != nil {
		t.Fatal(err)
	}
	if _, err := db.LogFeedback(ctx, FeedbackEvent{RequestID: "req-2", UserID: user, ItemID: "v2", Action: "skip", ModelID: "m"}); err != nil {
		t.Fatal(err)
	}
	if err := db.LogRecommendation(ctx, RecommendationLog{RequestID: "req-3", UserID: user, UserStatus: "known", ModelID: "m", TopK: 2, ItemIDs: []string{"v1", "v2"}, LatencyMs: 0.5}); err != nil {
		t.Fatal(err)
	}
	if err := db.LogAPIRequest(ctx, APIRequest{RequestID: "req-3", Method: "POST", Path: "/api/v1/recommendations", Status: 200, DurationMs: 1.2}); err != nil {
		t.Fatal(err)
	}
}

func verify(t *testing.T, db *DB, user string) {
	t.Helper()
	ctx := context.Background()
	events, err := db.ListFeedback(ctx, Filter{UserID: user})
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 2 || events[0].Action != "skip" || events[1].Rank == nil || *events[1].Rank != 2 {
		t.Fatalf("unexpected feedback rows: %+v", events)
	}
	recs, err := db.ListRecommendations(ctx, Filter{UserID: user})
	if err != nil || len(recs) != 1 || len(recs[0].ItemIDs) != 2 || recs[0].RequestID != "req-3" {
		t.Fatalf("unexpected recommendation logs: %v %+v", err, recs)
	}
	reqs, err := db.ListAPIRequests(ctx, Filter{RequestID: "req-3"})
	if err != nil || len(reqs) == 0 || reqs[0].Status != 200 {
		t.Fatalf("unexpected request logs: %v %+v", err, reqs)
	}
}

func TestMemoryStore(t *testing.T) {
	db, err := Open(context.Background(), ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	exercise(t, db, "u1")
	verify(t, db, "u1")
	summary, err := db.FeedbackSummary(context.Background())
	if err != nil || summary["play"] != 1 || summary["skip"] != 1 || summary["hide"] != 0 {
		t.Fatalf("unexpected summary: %v %#v", err, summary)
	}
}

func TestOpenRequiresURL(t *testing.T) {
	if _, err := Open(context.Background(), " "); err == nil {
		t.Fatal("expected an error for an empty DATABASE_URL")
	}
}

// TestPostgresPersistsAcrossReconnect is the Day 10 exit criterion ("feedback
// survives server restart, logs are queryable") at the storage layer. It runs
// only when TEST_DATABASE_URL points at a disposable PostgreSQL database.
func TestPostgresPersistsAcrossReconnect(t *testing.T) {
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	ctx := context.Background()
	user := "it-" + time.Now().Format("150405.000000")
	first, err := Open(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	exercise(t, first, user)
	if err := first.Close(); err != nil {
		t.Fatal(err)
	}
	second, err := Open(ctx, url) // simulates an API restart: new pool, schema re-applied
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	verify(t, second, user)
}
