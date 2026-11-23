package config

import (
	"os"
	"strconv"
)

type Config struct {
	Port           string
	DataDir        string
	DBPath         string
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
		dataDir = "./testdata"
	}

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "./recommendations.db"
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
		DBPath:         dbPath,
		AllowedOrigins: []string{"http://localhost:3000", "http://127.0.0.1:3000", "*"},
		DefaultTopK:    topK,
	}
}
