// Package config reads runtime settings from environment variables.
package config

import (
	"os"
	"strconv"
	"strings"
)

// Config holds runtime settings.
type Config struct {
	Port               string
	DataDir            string
	DatabaseURL        string
	AllowedOrigins     []string
	RateLimitPerMinute int
	AdminToken         string
	LogRequestsToDB    bool
}

// Load reads the environment, applying documented defaults.
func Load() Config {
	cfg := Config{
		Port:               getenv("PORT", "8080"),
		DataDir:            getenv("DATA_DIR", "./serving_data"),
		DatabaseURL:        os.Getenv("DATABASE_URL"),
		AllowedOrigins:     []string{"http://localhost:3000", "http://127.0.0.1:3000"},
		RateLimitPerMinute: 300,
		AdminToken:         os.Getenv("ADMIN_TOKEN"),
		LogRequestsToDB:    getenv("LOG_REQUESTS_TO_DB", "true") != "false",
	}
	if value := strings.TrimSpace(os.Getenv("ALLOWED_ORIGINS")); value != "" {
		cfg.AllowedOrigins = nil
		for _, origin := range strings.Split(value, ",") {
			if origin = strings.TrimSpace(origin); origin != "" {
				cfg.AllowedOrigins = append(cfg.AllowedOrigins, origin)
			}
		}
	}
	if value, err := strconv.Atoi(os.Getenv("RATE_LIMIT_PER_MINUTE")); err == nil && value > 0 {
		cfg.RateLimitPerMinute = value
	}
	return cfg
}

func getenv(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
