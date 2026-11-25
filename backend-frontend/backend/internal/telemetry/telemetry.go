package telemetry

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strconv"
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
	TotalLatencyNanoseconds atomic.Uint64
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
		GlobalMetrics.TotalLatencyNanoseconds.Add(uint64(duration.Nanoseconds()))

		if lrw.statusCode >= 500 {
			GlobalMetrics.ErrorCount.Add(1)
		}
		lrw.Header().Set("X-Response-Time-Ms", strconv.FormatFloat(float64(duration.Microseconds())/1000, 'f', 3, 64))
		w.WriteHeader(lrw.statusCode)
		_, _ = lrw.body.WriteTo(w)
	})
}

type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
	wroteHeader bool
	body bytes.Buffer
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	if lrw.wroteHeader { return }
	lrw.wroteHeader = true
	lrw.statusCode = code
}

func (lrw *loggingResponseWriter) Write(p []byte) (int, error) {
	if !lrw.wroteHeader { lrw.WriteHeader(http.StatusOK) }
	return lrw.body.Write(p)
}
