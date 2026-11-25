package main

import (
	"context"
	"fmt"
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
	// Structured logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	cfg := config.Load()
	slog.Info("Starting KuaiRec Recommender API",
		"port", cfg.Port,
		"data_dir", cfg.DataDir,
		"database", "postgresql",
	)

	// Load Video Catalog
	catalogPath := filepath.Join(cfg.DataDir, "catalog.json")
	catRepo, err := catalog.NewRepository(catalogPath)
	if err != nil {
		slog.Error("Fatal: Failed to load catalog", "path", catalogPath, "error", err)
		os.Exit(1)
	}
	slog.Info("Video catalog loaded successfully", "items_count", catRepo.Count())

	// Initialize Recommender Engine
	recEngine, err := recommender.NewEngine(cfg.DataDir, catRepo)
	if err != nil {
		slog.Error("Fatal: Failed to initialize recommender engine", "error", err)
		os.Exit(1)
	}
	slog.Info("Recommender engine initialized", "active_model", recEngine.GetActiveModel())

	// Initialize PostgreSQL persistence.
	db, err := database.Open(cfg.DatabaseURL)
	if err != nil {
		slog.Error("Fatal: Failed to open database", "error", err)
		os.Exit(1)
	}
	defer db.Close()
	slog.Info("Database connection initialized successfully")

	// Create HTTP Router
	handler := httpapi.NewHandler(recEngine, catRepo, db, cfg.DataDir)
	router := httpapi.NewRouter(handler, cfg.AllowedOrigins)

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Server run context
	serverErrors := make(chan error, 1)
	go func() {
		slog.Info(fmt.Sprintf("KuaiRec API listening on http://0.0.0.0:%s", cfg.Port))
		serverErrors <- srv.ListenAndServe()
	}()

	// Graceful shutdown
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, os.Interrupt, syscall.SIGTERM)

	select {
	case err := <-serverErrors:
		if err != nil && err != http.ErrServerClosed {
			slog.Error("Server error", "error", err)
		}
	case sig := <-shutdown:
		slog.Info("Received shutdown signal", "signal", sig.String())
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		if err := srv.Shutdown(ctx); err != nil {
			slog.Error("Graceful shutdown failed, forcing close", "error", err)
			_ = srv.Close()
		}
		slog.Info("Server stopped cleanly")
	}
}
