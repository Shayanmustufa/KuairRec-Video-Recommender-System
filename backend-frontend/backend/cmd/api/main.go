// Command api serves the frozen KuaiRec recommendation artifacts over HTTP.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/config"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/database"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/httpapi"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/recommender"
)

func main() {
	level := slog.LevelInfo
	if os.Getenv("LOG_LEVEL") == "debug" {
		level = slog.LevelDebug
	}
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level})))
	if err := run(); err != nil {
		slog.Error("fatal", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	started := time.Now()
	repo, err := catalog.NewRepository(filepath.Join(cfg.DataDir, "catalog.json"))
	if err != nil {
		return err
	}
	engine, err := recommender.NewEngine(cfg.DataDir, repo)
	if err != nil {
		return err
	}
	manifest := engine.Manifest()
	slog.Info("serving bundle loaded", "data_dir", cfg.DataDir, "catalog_items", repo.Count(),
		"known_users", engine.UserCount(), "model", manifest.CurrentModel,
		"bundle_checksums_verified", manifest.BundleVerifiedAtLoad, "load_ms", time.Since(started).Milliseconds())

	db, err := database.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer db.Close()
	slog.Info("database ready", "kind", db.Kind())

	handler, err := httpapi.NewHandler(engine, repo, db, httpapi.Options{
		DataDir: cfg.DataDir, AdminToken: cfg.AdminToken, LogRequestsToDB: cfg.LogRequestsToDB})
	if err != nil {
		return err
	}
	srv := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           httpapi.NewRouter(handler, httpapi.RouterOptions{AllowedOrigins: cfg.AllowedOrigins, RateLimitPerMinute: cfg.RateLimitPerMinute}),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	errs := make(chan error, 1)
	go func() {
		slog.Info("listening", "addr", srv.Addr, "allowed_origins", cfg.AllowedOrigins, "rate_limit_per_minute", cfg.RateLimitPerMinute)
		errs <- srv.ListenAndServe()
	}()
	select {
	case err := <-errs:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case <-ctx.Done():
		slog.Info("shutdown signal received")
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	err = srv.Shutdown(shutdownCtx)
	handler.Wait()
	slog.Info("server stopped")
	return err
}
