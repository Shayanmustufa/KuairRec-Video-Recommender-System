package config

import (
	"os"
	"strconv"
	"strings"
)

type Config struct {
	Port           string
	DataDir        string
	DatabaseURL    string
	AllowedOrigins []string
	DefaultTopK    int
}

func Load() *Config {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	dataDir := os.Getenv("DATA_DIR")
	if dataDir == "" {
		dataDir = "./serving_data"
	}

	databaseURL := os.Getenv("DATABASE_URL")

	allowedOrigins := []string{"http://localhost:3000", "http://127.0.0.1:3000"}
	if value := strings.TrimSpace(os.Getenv("ALLOWED_ORIGINS")); value != "" {
		allowedOrigins = nil
		for _, origin := range strings.Split(value, ",") {
			if origin = strings.TrimSpace(origin); origin != "" { allowedOrigins = append(allowedOrigins, origin) }
		}
	}

	topKStr := os.Getenv("DEFAULT_TOP_K")
	topK := 10
	if topKStr != "" {
		if val, err := strconv.Atoi(topKStr); err == nil && val > 0 {
			topK = val
		}
	}

	return &Config{
		Port:           port,
		DataDir:        dataDir,
		DatabaseURL:    databaseURL,
		AllowedOrigins: allowedOrigins,
		DefaultTopK:    topK,
	}
}
