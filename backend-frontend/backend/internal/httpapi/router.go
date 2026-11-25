package httpapi

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/cors"
	"github.com/go-chi/httprate"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/telemetry"
)

// RouterOptions configures cross-cutting middleware.
type RouterOptions struct {
	AllowedOrigins     []string
	RateLimitPerMinute int
}

// NewRouter wires routes and middleware. Order: request ID → access log
// (status, latency, persistence) → panic recovery → CORS → routes. The API
// group is rate limited per client IP.
func NewRouter(h *Handler, opts RouterOptions) http.Handler {
	r := chi.NewRouter()
	r.Use(telemetry.RequestIDMiddleware)
	r.Use(h.AccessLog)
	r.Use(Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   opts.AllowedOrigins,
		AllowedMethods:   []string{http.MethodGet, http.MethodPost, http.MethodOptions},
		AllowedHeaders:   []string{"Content-Type", telemetry.HeaderRequestID, "X-Admin-Token"},
		ExposedHeaders:   []string{telemetry.HeaderRequestID, telemetry.HeaderResponseTime},
		AllowCredentials: false,
		MaxAge:           300,
	}))
	r.NotFound(func(w http.ResponseWriter, r *http.Request) { writeError(w, http.StatusNotFound, "route not found") })
	r.MethodNotAllowed(func(w http.ResponseWriter, r *http.Request) {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
	})

	r.Get("/healthz", h.Healthz)
	r.Get("/readyz", h.Readyz)
	r.Get("/metrics", h.Metrics)

	r.Route("/api/v1", func(api chi.Router) {
		if opts.RateLimitPerMinute > 0 {
			api.Use(httprate.Limit(opts.RateLimitPerMinute, time.Minute,
				httprate.WithKeyFuncs(httprate.KeyByRealIP),
				httprate.WithLimitHandler(func(w http.ResponseWriter, r *http.Request) {
					writeError(w, http.StatusTooManyRequests, "rate limit exceeded; retry later")
				}),
			))
		}
		api.Post("/recommendations", h.Recommend)
		api.Post("/feedback", h.CreateFeedback)
		api.Get("/feedback", h.ListFeedback)
		api.Get("/models", h.ListModels)
		api.Get("/models/current", h.CurrentModel)
		api.Post("/models/switch", h.SwitchModel)
		api.Get("/compare", h.Compare)
		api.Get("/users", h.ListUsers)
		api.Get("/users/{userID}", h.GetUser)
		api.Get("/videos/{videoID}", h.GetVideo)
		api.Get("/videos/{videoID}/similar", h.GetSimilarVideos)
		api.Get("/metrics/offline", h.OfflineMetrics)
		api.Get("/logs/requests", h.ListRequestLogs)
		api.Get("/logs/recommendations", h.ListRecommendationLogs)
	})
	return r
}
