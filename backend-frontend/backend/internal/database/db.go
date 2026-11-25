package database

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"sync"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

type FeedbackEvent struct {
	ID        int64     `json:"id"`
	UserID    string    `json:"user_id"`
	ItemID    string    `json:"item_id"`
	Action    string    `json:"action"` // "click", "play", "skip", "hide"
	ModelID   string    `json:"model_id"`
	CreatedAt time.Time `json:"created_at"`
}

type RecommendationLog struct {
	ID            int64     `json:"id"`
	RequestID     string    `json:"request_id"`
	UserID        string    `json:"user_id"`
	ModelID       string    `json:"model_id"`
	TopK          int       `json:"top_k"`
	IsFallback    bool      `json:"is_fallback"`
	RecommendedAt time.Time `json:"recommended_at"`
}

type DB struct {
	sqlDB   *sql.DB
	memory  bool
	mu      sync.Mutex
	feedback []FeedbackEvent
	recommendations []RecommendationLog
}

func Open(databaseURL string) (*DB, error) {
	databaseURL = strings.TrimSpace(databaseURL)
	// A deterministic in-memory store keeps unit tests independent of a local
	// PostgreSQL service. Production configuration must use PostgreSQL.
	if strings.EqualFold(databaseURL, ":memory:") || strings.EqualFold(databaseURL, "memory://") {
		return &DB{memory: true}, nil
	}
	if databaseURL == "" {
		return nil, errors.New("DATABASE_URL is required (use a PostgreSQL connection URL)")
	}
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		_ = db.Close()
		return nil, err
	}

	schema := `
	CREATE TABLE IF NOT EXISTS feedback_events (
		id BIGSERIAL PRIMARY KEY,
		user_id TEXT NOT NULL,
		item_id TEXT NOT NULL,
		action TEXT NOT NULL,
		model_id TEXT NOT NULL,
		created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS recommendation_logs (
		id BIGSERIAL PRIMARY KEY,
		request_id TEXT NOT NULL,
		user_id TEXT NOT NULL,
		model_id TEXT NOT NULL,
		top_k INTEGER NOT NULL,
		is_fallback BOOLEAN NOT NULL,
		recommended_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
	);

	CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id);
	CREATE INDEX IF NOT EXISTS idx_feedback_item ON feedback_events(item_id);
	`

	if _, err := db.ExecContext(ctx, schema); err != nil {
		_ = db.Close()
		return nil, err
	}

	return &DB{sqlDB: db}, nil
}

func (d *DB) LogFeedback(ctx context.Context, userID, itemID, action, modelID string) error {
	now := time.Now().UTC()
	if d == nil { return errors.New("database is unavailable") }
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		d.feedback = append(d.feedback, FeedbackEvent{ID: int64(len(d.feedback) + 1), UserID: userID, ItemID: itemID, Action: action, ModelID: modelID, CreatedAt: now})
		return nil
	}
	if d.sqlDB != nil {
		query := `INSERT INTO feedback_events (user_id, item_id, action, model_id, created_at) VALUES ($1, $2, $3, $4, $5)`
		_, err := d.sqlDB.ExecContext(ctx, query, userID, itemID, action, modelID, now)
		if err == nil {
			return nil
		}
		return err
	}
	return sql.ErrConnDone
}

func (d *DB) LogRecommendation(ctx context.Context, requestID, userID, modelID string, topK int, isFallback bool) error {
	now := time.Now().UTC()
	if d == nil { return errors.New("database is unavailable") }
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		d.recommendations = append(d.recommendations, RecommendationLog{ID: int64(len(d.recommendations) + 1), RequestID: requestID, UserID: userID, ModelID: modelID, TopK: topK, IsFallback: isFallback, RecommendedAt: now})
		return nil
	}
	if d.sqlDB != nil {
		query := `INSERT INTO recommendation_logs (request_id, user_id, model_id, top_k, is_fallback, recommended_at) VALUES ($1, $2, $3, $4, $5, $6)`
		_, err := d.sqlDB.ExecContext(ctx, query, requestID, userID, modelID, topK, isFallback, now)
		if err == nil {
			return nil
		}
	}

	return sql.ErrConnDone
}

func (d *DB) GetFeedbackSummary(ctx context.Context) (map[string]int, error) {
	summary := map[string]int{"click": 0, "play": 0, "skip": 0, "hide": 0}
	if d == nil { return summary, errors.New("database is unavailable") }
	if d.memory {
		d.mu.Lock()
		defer d.mu.Unlock()
		for _, event := range d.feedback { summary[event.Action]++ }
		return summary, nil
	}

	if d.sqlDB != nil {
		rows, err := d.sqlDB.QueryContext(ctx, `SELECT action, COUNT(*) FROM feedback_events GROUP BY action`)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var action string
				var count int
				if err := rows.Scan(&action, &count); err == nil {
					summary[action] = count
				}
			}
			return summary, rows.Err()
		}
	}

	return summary, nil
}

func (d *DB) Ping(ctx context.Context) error {
	if d == nil { return errors.New("database is unavailable") }
	if d.memory { return nil }
	if d.sqlDB == nil { return errors.New("database is unavailable") }
	return d.sqlDB.PingContext(ctx)
}

func (d *DB) Close() error {
	if d != nil && d.sqlDB != nil {
		return d.sqlDB.Close()
	}
	return nil
}
