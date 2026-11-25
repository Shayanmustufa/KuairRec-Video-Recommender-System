// Package database persists feedback, recommendation metadata and API request
// logs in PostgreSQL. A ":memory:" URL selects an in-process store used only by
// unit tests.
package database

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"strings"
	"sync"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib" // PostgreSQL driver
)

// FeedbackEvent is one displayed-item interaction. It is stored for analysis
// only; no model is retrained from it (WBS §7).
type FeedbackEvent struct {
	ID        int64     `json:"id"`
	RequestID string    `json:"request_id"`
	UserID    string    `json:"user_id"`
	ItemID    string    `json:"item_id"`
	Action    string    `json:"action"`
	ModelID   string    `json:"model_id"`
	Rank      *int      `json:"rank,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

// RecommendationLog stores the metadata of one served recommendation list.
type RecommendationLog struct {
	ID         int64     `json:"id"`
	RequestID  string    `json:"request_id"`
	UserID     string    `json:"user_id"`
	UserStatus string    `json:"user_status"`
	ModelID    string    `json:"model_id"`
	TopK       int       `json:"top_k"`
	IsFallback bool      `json:"is_fallback"`
	ItemIDs    []string  `json:"item_ids"`
	LatencyMs  float64   `json:"latency_ms"`
	CreatedAt  time.Time `json:"created_at"`
}

// APIRequest is one HTTP request log row.
type APIRequest struct {
	ID         int64     `json:"id"`
	RequestID  string    `json:"request_id"`
	Method     string    `json:"method"`
	Path       string    `json:"path"`
	Status     int       `json:"status"`
	DurationMs float64   `json:"duration_ms"`
	RemoteAddr string    `json:"remote_addr"`
	CreatedAt  time.Time `json:"created_at"`
}

// Filter narrows list queries.
type Filter struct {
	UserID    string
	RequestID string
	Limit     int
}

func (f Filter) limit() int {
	if f.Limit <= 0 || f.Limit > 500 {
		return 100
	}
	return f.Limit
}

// DB is either a PostgreSQL connection pool or the in-memory test store.
type DB struct {
	sqlDB *sql.DB

	memory          bool
	mu              sync.Mutex
	feedback        []FeedbackEvent
	recommendations []RecommendationLog
	requests        []APIRequest
}

// Schema is the PostgreSQL DDL applied at startup (idempotent).
const Schema = `
CREATE TABLE IF NOT EXISTS feedback_events (
	id BIGSERIAL PRIMARY KEY,
	request_id TEXT NOT NULL DEFAULT '',
	user_id TEXT NOT NULL,
	item_id TEXT NOT NULL,
	action TEXT NOT NULL CHECK (action IN ('click', 'play', 'skip', 'hide')),
	model_id TEXT NOT NULL,
	rank INTEGER,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_item ON feedback_events(item_id);
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '';
ALTER TABLE feedback_events ADD COLUMN IF NOT EXISTS rank INTEGER;

CREATE TABLE IF NOT EXISTS recommendation_logs (
	id BIGSERIAL PRIMARY KEY,
	request_id TEXT NOT NULL,
	user_id TEXT NOT NULL,
	user_status TEXT NOT NULL DEFAULT '',
	model_id TEXT NOT NULL,
	top_k INTEGER NOT NULL,
	is_fallback BOOLEAN NOT NULL,
	item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
	latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
	recommended_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_user ON recommendation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_request ON recommendation_logs(request_id);
ALTER TABLE recommendation_logs ADD COLUMN IF NOT EXISTS user_status TEXT NOT NULL DEFAULT '';
ALTER TABLE recommendation_logs ADD COLUMN IF NOT EXISTS item_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE recommendation_logs ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS api_requests (
	id BIGSERIAL PRIMARY KEY,
	request_id TEXT NOT NULL,
	method TEXT NOT NULL,
	path TEXT NOT NULL,
	status INTEGER NOT NULL,
	duration_ms DOUBLE PRECISION NOT NULL,
	remote_addr TEXT NOT NULL DEFAULT '',
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_requests_created ON api_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_requests_request ON api_requests(request_id);
`

// Open connects to PostgreSQL and applies the schema. ":memory:" returns the
// test store.
func Open(ctx context.Context, databaseURL string) (*DB, error) {
	databaseURL = strings.TrimSpace(databaseURL)
	if strings.EqualFold(databaseURL, ":memory:") || strings.EqualFold(databaseURL, "memory://") {
		return &DB{memory: true}, nil
	}
	if databaseURL == "" {
		return nil, errors.New("DATABASE_URL is required (PostgreSQL connection URL)")
	}
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(10)
	db.SetConnMaxIdleTime(5 * time.Minute)
	var lastErr error
	for attempt := 0; attempt < 10; attempt++ { // tolerate PostgreSQL starting up
		pingCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
		lastErr = db.PingContext(pingCtx)
		cancel()
		if lastErr == nil {
			break
		}
		select {
		case <-ctx.Done():
			_ = db.Close()
			return nil, ctx.Err()
		case <-time.After(time.Second):
		}
	}
	if lastErr != nil {
		_ = db.Close()
		return nil, lastErr
	}
	if _, err := db.ExecContext(ctx, Schema); err != nil {
		_ = db.Close()
		return nil, err
	}
	return &DB{sqlDB: db}, nil
}

var errUnavailable = errors.New("database is unavailable")

// LogFeedback stores one feedback event.
func (d *DB) LogFeedback(ctx context.Context, e FeedbackEvent) (FeedbackEvent, error) {
	if d == nil {
		return e, errUnavailable
	}
	e.CreatedAt = time.Now().UTC()
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		e.ID = int64(len(d.feedback) + 1)
		d.feedback = append(d.feedback, e)
		return e, nil
	}
	err := d.sqlDB.QueryRowContext(ctx,
		`INSERT INTO feedback_events (request_id, user_id, item_id, action, model_id, rank, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`,
		e.RequestID, e.UserID, e.ItemID, e.Action, e.ModelID, e.Rank, e.CreatedAt).Scan(&e.ID)
	return e, err
}

// LogRecommendation stores recommendation metadata.
func (d *DB) LogRecommendation(ctx context.Context, r RecommendationLog) error {
	if d == nil {
		return errUnavailable
	}
	r.CreatedAt = time.Now().UTC()
	if r.ItemIDs == nil {
		r.ItemIDs = []string{}
	}
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		r.ID = int64(len(d.recommendations) + 1)
		d.recommendations = append(d.recommendations, r)
		return nil
	}
	items, _ := json.Marshal(r.ItemIDs)
	_, err := d.sqlDB.ExecContext(ctx,
		`INSERT INTO recommendation_logs (request_id, user_id, user_status, model_id, top_k, is_fallback, item_ids, latency_ms, recommended_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)`,
		r.RequestID, r.UserID, r.UserStatus, r.ModelID, r.TopK, r.IsFallback, string(items), r.LatencyMs, r.CreatedAt)
	return err
}

// LogAPIRequest stores one HTTP request log row.
func (d *DB) LogAPIRequest(ctx context.Context, r APIRequest) error {
	if d == nil {
		return errUnavailable
	}
	r.CreatedAt = time.Now().UTC()
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		r.ID = int64(len(d.requests) + 1)
		d.requests = append(d.requests, r)
		return nil
	}
	_, err := d.sqlDB.ExecContext(ctx,
		`INSERT INTO api_requests (request_id, method, path, status, duration_ms, remote_addr, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		r.RequestID, r.Method, r.Path, r.Status, r.DurationMs, r.RemoteAddr, r.CreatedAt)
	return err
}

// ListFeedback returns newest feedback first.
func (d *DB) ListFeedback(ctx context.Context, f Filter) ([]FeedbackEvent, error) {
	if d == nil {
		return nil, errUnavailable
	}
	out := []FeedbackEvent{}
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		for i := len(d.feedback) - 1; i >= 0 && len(out) < f.limit(); i-- {
			e := d.feedback[i]
			if (f.UserID == "" || e.UserID == f.UserID) && (f.RequestID == "" || e.RequestID == f.RequestID) {
				out = append(out, e)
			}
		}
		return out, nil
	}
	rows, err := d.sqlDB.QueryContext(ctx,
		`SELECT id, request_id, user_id, item_id, action, model_id, rank, created_at FROM feedback_events
		 WHERE ($1 = '' OR user_id = $1) AND ($2 = '' OR request_id = $2)
		 ORDER BY id DESC LIMIT $3`, f.UserID, f.RequestID, f.limit())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var e FeedbackEvent
		var rank sql.NullInt32
		if err := rows.Scan(&e.ID, &e.RequestID, &e.UserID, &e.ItemID, &e.Action, &e.ModelID, &rank, &e.CreatedAt); err != nil {
			return nil, err
		}
		if rank.Valid {
			v := int(rank.Int32)
			e.Rank = &v
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ListRecommendations returns newest recommendation logs first.
func (d *DB) ListRecommendations(ctx context.Context, f Filter) ([]RecommendationLog, error) {
	if d == nil {
		return nil, errUnavailable
	}
	out := []RecommendationLog{}
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		for i := len(d.recommendations) - 1; i >= 0 && len(out) < f.limit(); i-- {
			r := d.recommendations[i]
			if (f.UserID == "" || r.UserID == f.UserID) && (f.RequestID == "" || r.RequestID == f.RequestID) {
				out = append(out, r)
			}
		}
		return out, nil
	}
	rows, err := d.sqlDB.QueryContext(ctx,
		`SELECT id, request_id, user_id, user_status, model_id, top_k, is_fallback, item_ids, latency_ms, recommended_at
		 FROM recommendation_logs WHERE ($1 = '' OR user_id = $1) AND ($2 = '' OR request_id = $2)
		 ORDER BY id DESC LIMIT $3`, f.UserID, f.RequestID, f.limit())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var r RecommendationLog
		var items []byte
		if err := rows.Scan(&r.ID, &r.RequestID, &r.UserID, &r.UserStatus, &r.ModelID, &r.TopK, &r.IsFallback, &items, &r.LatencyMs, &r.CreatedAt); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(items, &r.ItemIDs); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// ListAPIRequests returns newest API request logs first.
func (d *DB) ListAPIRequests(ctx context.Context, f Filter) ([]APIRequest, error) {
	if d == nil {
		return nil, errUnavailable
	}
	out := []APIRequest{}
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		for i := len(d.requests) - 1; i >= 0 && len(out) < f.limit(); i-- {
			if f.RequestID == "" || d.requests[i].RequestID == f.RequestID {
				out = append(out, d.requests[i])
			}
		}
		return out, nil
	}
	rows, err := d.sqlDB.QueryContext(ctx,
		`SELECT id, request_id, method, path, status, duration_ms, remote_addr, created_at FROM api_requests
		 WHERE ($1 = '' OR request_id = $1) ORDER BY id DESC LIMIT $2`, f.RequestID, f.limit())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var r APIRequest
		if err := rows.Scan(&r.ID, &r.RequestID, &r.Method, &r.Path, &r.Status, &r.DurationMs, &r.RemoteAddr, &r.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// FeedbackSummary counts feedback events per action.
func (d *DB) FeedbackSummary(ctx context.Context) (map[string]int, error) {
	summary := map[string]int{"click": 0, "play": 0, "skip": 0, "hide": 0}
	if d == nil {
		return summary, errUnavailable
	}
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		for _, e := range d.feedback {
			summary[e.Action]++
		}
		return summary, nil
	}
	rows, err := d.sqlDB.QueryContext(ctx, `SELECT action, COUNT(*) FROM feedback_events GROUP BY action`)
	if err != nil {
		return summary, err
	}
	defer rows.Close()
	for rows.Next() {
		var action string
		var count int
		if err := rows.Scan(&action, &count); err != nil {
			return summary, err
		}
		summary[action] = count
	}
	return summary, rows.Err()
}

// Ping checks connectivity.
func (d *DB) Ping(ctx context.Context) error {
	switch {
	case d == nil:
		return errUnavailable
	case d.memory:
		return nil
	default:
		return d.sqlDB.PingContext(ctx)
	}
}

// Kind reports "postgresql" or "memory".
func (d *DB) Kind() string {
	if d != nil && d.memory {
		return "memory"
	}
	return "postgresql"
}

// Close releases the connection pool.
func (d *DB) Close() error {
	if d != nil && d.sqlDB != nil {
		return d.sqlDB.Close()
	}
	return nil
}
