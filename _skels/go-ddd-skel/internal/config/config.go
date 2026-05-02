// Package config loads the wrapper-shared environment into a typed
// Config struct. Reads <wrapper>/.env first (so DATABASE_URL,
// JWT_SECRET, and friends are inherited from the project root) then
// the local service .env for overrides. Handlers consume Config via
// dependency injection from main.go — they never call os.Getenv
// directly.
package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Config is the strongly-typed snapshot of every wrapper-shared env
// var the service consults. Fields mirror the actix / axum / spring
// skels so a token issued by any backend in the wrapper roundtrips
// through this one.
type Config struct {
	DatabaseURL    string
	JWTSecret      string
	JWTAlgorithm   string
	JWTIssuer      string
	JWTAccessTTL   int64
	JWTRefreshTTL  int64
	ServiceHost    string
	ServicePort    int
}

// FromEnv builds a Config from process env after sourcing the
// wrapper-shared .env (parent dir) and the local .env (cwd).
// Defaults keep the skeleton runnable on a bare clone.
func FromEnv() Config {
	loadDotenv()
	return Config{
		DatabaseURL:   normalizeSQLiteURL(getenv("DATABASE_URL", "sqlite://./service.db")),
		JWTSecret:     getenv("JWT_SECRET", "change-me-32-bytes-of-random-data"),
		JWTAlgorithm:  getenv("JWT_ALGORITHM", "HS256"),
		JWTIssuer:     getenv("JWT_ISSUER", "devskel"),
		JWTAccessTTL:  getenvInt64("JWT_ACCESS_TTL", 3600),
		JWTRefreshTTL: getenvInt64("JWT_REFRESH_TTL", 604800),
		ServiceHost:   getenv("SERVICE_HOST", "0.0.0.0"),
		ServicePort:   getenvInt("SERVICE_PORT", getenvInt("PORT", 8080)),
	}
}

// loadDotenv reads the wrapper-shared .env first, then the local one.
// Both calls are no-ops when the file is absent (godotenv returns an
// error we intentionally ignore — the env defaults take over).
func loadDotenv() {
	cwd, err := os.Getwd()
	if err == nil {
		wrapperEnv := filepath.Join(cwd, "..", ".env")
		if _, err := os.Stat(wrapperEnv); err == nil {
			_ = godotenv.Load(wrapperEnv)
		}
	}
	if _, err := os.Stat(".env"); err == nil {
		// Overload so the local .env wins over the wrapper .env.
		_ = godotenv.Overload(".env")
	}
}

// normalizeSQLiteURL translates the Python-flavored
// `sqlite:///<rel>` URL the wrapper ships (`SQLAlchemy` convention,
// triple slash = relative) into a `<wrapper>/<rel>` absolute path
// the modernc.org/sqlite driver understands.
//
// `modernc.org/sqlite` registers the driver name "sqlite" and accepts
// either a bare file path or a `file:` URI. We strip the `sqlite:`
// prefix entirely and resolve relative paths against the wrapper
// directory (cwd's parent by dev_skel convention) so every service
// in the same wrapper points at the identical file.
func normalizeSQLiteURL(raw string) string {
	if !strings.HasPrefix(raw, "sqlite:") {
		return raw
	}
	pathPart := raw
	for _, prefix := range []string{"sqlite:///", "sqlite://", "sqlite:"} {
		if strings.HasPrefix(pathPart, prefix) {
			pathPart = strings.TrimPrefix(pathPart, prefix)
			break
		}
	}
	if pathPart == ":memory:" {
		return ":memory:"
	}
	if filepath.IsAbs(pathPart) {
		return pathPart
	}
	cwd, err := os.Getwd()
	if err != nil {
		return pathPart
	}
	wrapperDir := filepath.Dir(cwd)
	return filepath.Join(wrapperDir, pathPart)
}

func getenv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}

func getenvInt(key string, fallback int) int {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func getenvInt64(key string, fallback int64) int64 {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			return n
		}
	}
	return fallback
}
