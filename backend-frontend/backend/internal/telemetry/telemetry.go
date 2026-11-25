// Package telemetry provides request IDs, response timing and process counters.
package telemetry

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"regexp"
	"strconv"
	"sync/atomic"
	"time"
)

type contextKey struct{}

// HeaderRequestID is propagated from clients when well-formed, else generated.
const HeaderRequestID = "X-Request-ID"

// HeaderResponseTime carries server processing time until headers were sent.
const HeaderResponseTime = "X-Response-Time-Ms"

var validRequestID = regexp.MustCompile(`^[A-Za-z0-9._-]{1,64}$`)

// Metrics holds process-lifetime counters exposed by GET /metrics.
type Metrics struct {
	StartedAt            time.Time
	TotalRequests        atomic.Uint64
	Status2xx            atomic.Uint64
	Status4xx            atomic.Uint64
	Status5xx            atomic.Uint64
	RateLimited          atomic.Uint64
	RecommendationsCount atomic.Uint64
	FallbackCount        atomic.Uint64
	FeedbackCount        atomic.Uint64
	TotalLatencyMicros   atomic.Uint64
}

// NewMetrics returns zeroed counters.
func NewMetrics() *Metrics { return &Metrics{StartedAt: time.Now()} }

// Snapshot returns a JSON-friendly view.
func (m *Metrics) Snapshot() map[string]any {
	total := m.TotalRequests.Load()
	avg := 0.0
	if total > 0 {
		avg = float64(m.TotalLatencyMicros.Load()) / float64(total) / 1000
	}
	return map[string]any{
		"uptime_seconds":         int64(time.Since(m.StartedAt).Seconds()),
		"total_requests":         total,
		"responses_2xx":          m.Status2xx.Load(),
		"responses_4xx":          m.Status4xx.Load(),
		"responses_5xx":          m.Status5xx.Load(),
		"rate_limited":           m.RateLimited.Load(),
		"recommendations_served": m.RecommendationsCount.Load(),
		"fallback_responses":     m.FallbackCount.Load(),
		"feedback_events_total":  m.FeedbackCount.Load(),
		"average_latency_ms":     avg,
	}
}

// RequestID returns the request ID stored in ctx.
func RequestID(ctx context.Context) string {
	id, _ := ctx.Value(contextKey{}).(string)
	return id
}

// WithRequestID stores id in ctx.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, contextKey{}, id)
}

func newRequestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// RequestIDMiddleware must run first so every later layer (logs, DB rows,
// handlers) sees the same ID.
func RequestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get(HeaderRequestID)
		if !validRequestID.MatchString(id) {
			id = newRequestID()
		}
		w.Header().Set(HeaderRequestID, id)
		next.ServeHTTP(w, r.WithContext(WithRequestID(r.Context(), id)))
	})
}

// StatusRecorder captures the status code and stamps the timing header when
// headers are written, without buffering the body.
type StatusRecorder struct {
	http.ResponseWriter
	Status int
	start  time.Time
	wrote  bool
}

// NewStatusRecorder wraps w.
func NewStatusRecorder(w http.ResponseWriter, start time.Time) *StatusRecorder {
	return &StatusRecorder{ResponseWriter: w, Status: http.StatusOK, start: start}
}

// WriteHeader records the status and sets X-Response-Time-Ms.
func (s *StatusRecorder) WriteHeader(code int) {
	if s.wrote {
		return
	}
	s.wrote = true
	s.Status = code
	elapsed := float64(time.Since(s.start).Microseconds()) / 1000
	s.ResponseWriter.Header().Set(HeaderResponseTime, strconv.FormatFloat(elapsed, 'f', 3, 64))
	s.ResponseWriter.WriteHeader(code)
}

// Write implies a 200 header if none was written.
func (s *StatusRecorder) Write(p []byte) (int, error) {
	if !s.wrote {
		s.WriteHeader(http.StatusOK)
	}
	return s.ResponseWriter.Write(p)
}

// Observe records one finished request.
func (m *Metrics) Observe(status int, duration time.Duration) {
	m.TotalRequests.Add(1)
	m.TotalLatencyMicros.Add(uint64(duration.Microseconds()))
	switch {
	case status >= 500:
		m.Status5xx.Add(1)
	case status >= 400:
		m.Status4xx.Add(1)
		if status == http.StatusTooManyRequests {
			m.RateLimited.Add(1)
		}
	default:
		m.Status2xx.Add(1)
	}
}
