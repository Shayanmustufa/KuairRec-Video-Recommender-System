package httpapi

import (
	"context"
	"log/slog"
	"net/http"
	"runtime/debug"
	"time"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

// AccessLog records status and latency, emits one structured JSON log line
// per request, and persists the request in the api_requests table.
func (h *Handler) AccessLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := telemetry.NewStatusRecorder(w, start)
		next.ServeHTTP(rec, r)
		duration := time.Since(start)
		h.metrics.Observe(rec.Status, duration)

		requestID := telemetry.RequestID(r.Context())
		durationMs := float64(duration.Microseconds()) / 1000
		probe := r.URL.Path == "/healthz" || r.URL.Path == "/readyz"
		level := slog.LevelInfo
		switch {
		case rec.Status >= 500:
			level = slog.LevelError
		case rec.Status >= 400:
			level = slog.LevelWarn
		case probe:
			level = slog.LevelDebug
		}
		slog.Log(r.Context(), level, "http_request",
			"request_id", requestID, "method", r.Method, "path", r.URL.Path,
			"status", rec.Status, "duration_ms", durationMs, "remote_addr", r.RemoteAddr)

		if probe || !h.logRequestsToDB || r.Method == http.MethodOptions {
			return
		}
		entry := database.APIRequest{RequestID: requestID, Method: r.Method, Path: r.URL.Path,
			Status: rec.Status, DurationMs: durationMs, RemoteAddr: r.RemoteAddr}
		h.background.Add(1)
		go func() {
			defer h.background.Done()
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			if err := h.db.LogAPIRequest(ctx, entry); err != nil {
				slog.Warn("api request log not persisted", "request_id", requestID, "error", err)
			}
		}()
	})
}

// Recoverer converts panics into a JSON 500 and logs the stack.
func Recoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				if rec == http.ErrAbortHandler {
					panic(rec)
				}
				slog.Error("panic recovered", "request_id", telemetry.RequestID(r.Context()),
					"panic", rec, "stack", string(debug.Stack()))
				writeError(w, http.StatusInternalServerError, "internal server error")
			}
		}()
		next.ServeHTTP(w, r)
	})
}
