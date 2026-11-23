package telemetry

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"sync/atomic"
	"time"
)

type contextKey string

const RequestIDKey contextKey = "request_id"

type MetricsCollector struct {
	TotalRequests        atomic.Uint64
	RecommendationsCount atomic.Uint64
	FeedbackCount        atomic.Uint64
	ErrorCount           atomic.Uint64
	TotalLatencyMs       atomic.Uint64
}

var GlobalMetrics = &MetricsCollector{}

func GenerateRequestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func RequestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reqID := r.Header.Get("X-Request-ID")
		if reqID == "" {
			reqID = GenerateRequestID()
		}
		ctx := context.WithValue(r.Context(), RequestIDKey, reqID)
		w.Header().Set("X-Request-ID", reqID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func LatencyAndMetricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		GlobalMetrics.TotalRequests.Add(1)

		lrw := &loggingResponseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(lrw, r)

		duration := time.Since(start)
		GlobalMetrics.TotalLatencyMs.Add(uint64(duration.Milliseconds()))

		if lrw.statusCode >= 500 {
			GlobalMetrics.ErrorCount.Add(1)
		}
		w.Header().Set("X-Response-Time-Ms", duration.String())
	})
}

type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	lrw.statusCode = code
	lrw.ResponseWriter.WriteHeader(code)
}
