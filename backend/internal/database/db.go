package database

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sync"
	"time"

	_ "modernc.org/sqlite"
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
	sqlDB *sql.DB
	// in-memory fallback if driver or file system has transient constraints
	mu             sync.RWMutex
	fallbackEvents []FeedbackEvent
	fallbackLogs   []RecommendationLog
}

func Open(dbPath string) (*DB, error) {
	if dir := filepath.Dir(dbPath); dir != "." && dir != "" {
		_ = os.MkdirAll(dir, 0755)
	}

	dsn := fmt.Sprintf("%s?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)", dbPath)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		slog.Warn("Failed to open SQLite database file, operating with safe in-memory fallback", "error", err)
		return &DB{}, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		slog.Warn("SQLite ping failed, falling back to in-memory store", "error", err)
		return &DB{}, nil
	}

	schema := `
	CREATE TABLE IF NOT EXISTS feedback_events (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id TEXT NOT NULL,
		item_id TEXT NOT NULL,
		action TEXT NOT NULL,
		model_id TEXT NOT NULL,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS recommendation_logs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		request_id TEXT NOT NULL,
		user_id TEXT NOT NULL,
		model_id TEXT NOT NULL,
		top_k INTEGER NOT NULL,
		is_fallback INTEGER NOT NULL,
		recommended_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);

	CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id);
	CREATE INDEX IF NOT EXISTS idx_feedback_item ON feedback_events(item_id);
	`

	if _, err := db.ExecContext(ctx, schema); err != nil {
		slog.Warn("Schema migration failed, falling back to in-memory store", "error", err)
		return &DB{}, nil
	}

	return &DB{sqlDB: db}, nil
}

func (d *DB) LogFeedback(ctx context.Context, userID, itemID, action, modelID string) error {
	now := time.Now().UTC()
	if d.sqlDB != nil {
		query := `INSERT INTO feedback_events (user_id, item_id, action, model_id, created_at) VALUES (?, ?, ?, ?, ?)`
		_, err := d.sqlDB.ExecContext(ctx, query, userID, itemID, action, modelID, now)
		if err == nil {
			return nil
		}
		slog.Warn("SQLite insert failed, recording to fallback store", "error", err)
	}

	d.mu.Lock()
	defer d.mu.Unlock()
	d.fallbackEvents = append(d.fallbackEvents, FeedbackEvent{
		ID:        int64(len(d.fallbackEvents) + 1),
		UserID:    userID,
		ItemID:    itemID,
		Action:    action,
		ModelID:   modelID,
		CreatedAt: now,
	})
	return nil
}

func (d *DB) LogRecommendation(ctx context.Context, requestID, userID, modelID string, topK int, isFallback bool) error {
	now := time.Now().UTC()
	if d.sqlDB != nil {
		query := `INSERT INTO recommendation_logs (request_id, user_id, model_id, top_k, is_fallback, recommended_at) VALUES (?, ?, ?, ?, ?, ?)`
		fallbackInt := 0
		if isFallback {
			fallbackInt = 1
		}
		_, err := d.sqlDB.ExecContext(ctx, query, requestID, userID, modelID, topK, fallbackInt, now)
		if err == nil {
			return nil
		}
	}

	d.mu.Lock()
	defer d.mu.Unlock()
	d.fallbackLogs = append(d.fallbackLogs, RecommendationLog{
		ID:            int64(len(d.fallbackLogs) + 1),
		RequestID:     requestID,
		UserID:        userID,
		ModelID:       modelID,
		TopK:          topK,
		IsFallback:    isFallback,
		RecommendedAt: now,
	})
	return nil
}

func (d *DB) GetFeedbackSummary(ctx context.Context) (map[string]int, error) {
	summary := map[string]int{"click": 0, "play": 0, "skip": 0, "hide": 0}

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
			return summary, nil
		}
	}

	d.mu.RLock()
	defer d.mu.RUnlock()
	for _, ev := range d.fallbackEvents {
		summary[ev.Action]++
	}
	return summary, nil
}

func (d *DB) Close() error {
	if d.sqlDB != nil {
		return d.sqlDB.Close()
	}
	return nil
}
