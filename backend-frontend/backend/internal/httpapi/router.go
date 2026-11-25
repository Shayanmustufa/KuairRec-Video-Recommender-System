package httpapi

import (
	"net/http"
	"strings"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

func NewRouter(h *Handler, allowedOrigins []string) http.Handler {
	mux := http.NewServeMux()

	// Health and observability routes
	mux.HandleFunc("/healthz", h.Healthz)
	mux.HandleFunc("/readyz", h.Readyz)
	mux.HandleFunc("/metrics", h.Metrics)

	// Recommendation and feedback routes
	mux.HandleFunc("/api/v1/recommendations", h.Recommend)
	mux.HandleFunc("/api/v1/feedback", h.Feedback)
	mux.HandleFunc("/api/v1/models", h.ListModels)
	mux.HandleFunc("/api/v1/models/current", h.CurrentModel)
	mux.HandleFunc("/api/v1/models/switch", h.SwitchModel)
	mux.HandleFunc("/api/v1/compare", h.Compare)
	mux.HandleFunc("/api/v1/users", h.ListUsers)
	mux.HandleFunc("/api/v1/metrics/offline", h.OfflineMetrics)

	// Dynamic video route handler
	mux.HandleFunc("/api/v1/videos/", func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/api/v1/videos/") {
			h.GetVideo(w, r)
			return
		}
		http.NotFound(w, r)
	})

	// Wrap middleware chain
	var handler http.Handler = mux
	handler = telemetry.LatencyAndMetricsMiddleware(handler)
	handler = telemetry.RequestIDMiddleware(handler)
	handler = LoggingMiddleware(handler)
	handler = RecoveryMiddleware(handler)
	handler = CorsMiddleware(allowedOrigins)(handler)

	return handler
}
