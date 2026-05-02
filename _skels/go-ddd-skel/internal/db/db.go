// Package db opens a GORM-managed database connection (SQLite or
// PostgreSQL) and runs `AutoMigrate` for the wrapper-shared
// entities. The driver is auto-detected from the DATABASE_URL scheme
// and the same migration set runs for either backend.
package db

import (
	"strings"

	// glebarez/sqlite — pure-Go SQLite driver wired into GORM.
	// Matches the existing modernc.org/sqlite base so the binary
	// stays cgo-free.
	"github.com/glebarez/sqlite"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/example/go-ddd-skel/internal/models"
)

// Open returns a *gorm.DB after running AutoMigrate. Accepts a full
// URL (postgresql://..., sqlite:///...) or a bare path.
func Open(dsn string) (*gorm.DB, error) {
	cfg := &gorm.Config{
		// Suppress the noisy "record not found" logger by default —
		// handlers translate gorm.ErrRecordNotFound into 404
		// responses themselves.
		Logger: logger.Default.LogMode(logger.Warn),
	}

	conn, err := openDialect(dsn, cfg)
	if err != nil {
		return nil, err
	}

	// SQLite needs explicit FK enforcement (it ships OFF by default)
	// and we cap the pool at 1 because modernc.org/sqlite serialises
	// writes regardless.
	if isSQLite(dsn) {
		if err := conn.Exec("PRAGMA foreign_keys = ON").Error; err != nil {
			return nil, err
		}
		sqlDB, err := conn.DB()
		if err != nil {
			return nil, err
		}
		sqlDB.SetMaxOpenConns(1)
	}

	if err := conn.AutoMigrate(models.All()...); err != nil {
		return nil, err
	}
	return conn, nil
}

func openDialect(dsn string, cfg *gorm.Config) (*gorm.DB, error) {
	if isPostgres(dsn) {
		return gorm.Open(postgres.Open(dsn), cfg)
	}
	// Strip the various ``sqlite://`` prefix forms before handing
	// the path to the GORM SQLite driver (which expects a plain
	// file path or ``:memory:``).
	path := dsn
	for _, prefix := range []string{"sqlite:///", "sqlite://", "sqlite:"} {
		if strings.HasPrefix(path, prefix) {
			path = strings.TrimPrefix(path, prefix)
			break
		}
	}
	return gorm.Open(sqlite.Open(path), cfg)
}

func isPostgres(dsn string) bool {
	return strings.HasPrefix(dsn, "postgresql://") ||
		strings.HasPrefix(dsn, "postgres://")
}

func isSQLite(dsn string) bool {
	return !isPostgres(dsn)
}
