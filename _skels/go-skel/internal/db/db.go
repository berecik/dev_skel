// Package db opens a database connection (SQLite or PostgreSQL) and
// runs idempotent CREATE TABLE IF NOT EXISTS for the wrapper-shared
// tables. The driver is auto-detected from the DATABASE_URL scheme.
package db

import (
	"database/sql"
	"strings"

	_ "github.com/lib/pq"    // registers the "postgres" driver
	_ "modernc.org/sqlite"   // registers the "sqlite" driver
)

// Open returns a *sql.DB after running the schema bootstrap.
// Accepts a full URL (postgresql://..., sqlite:///...) or a bare path.
func Open(dsn string) (*sql.DB, error) {
	driver, connStr := detectDriver(dsn)

	conn, err := sql.Open(driver, connStr)
	if err != nil {
		return nil, err
	}

	if driver == "sqlite" {
		// modernc.org/sqlite recommends a single connection because
		// the underlying driver serialises writes anyway.
		conn.SetMaxOpenConns(1)
		// Enable foreign key enforcement — SQLite defaults to OFF.
		if _, err := conn.Exec("PRAGMA foreign_keys = ON"); err != nil {
			_ = conn.Close()
			return nil, err
		}
	}

	if err := initSchema(conn, driver); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return conn, nil
}

// detectDriver returns the sql driver name and connection string.
func detectDriver(dsn string) (string, string) {
	if strings.HasPrefix(dsn, "postgresql://") || strings.HasPrefix(dsn, "postgres://") {
		return "postgres", dsn
	}
	// Strip sqlite: prefix variants for the modernc driver
	path := dsn
	for _, prefix := range []string{"sqlite:///", "sqlite://", "sqlite:"} {
		if strings.HasPrefix(path, prefix) {
			path = strings.TrimPrefix(path, prefix)
			break
		}
	}
	return "sqlite", path
}

func initSchema(conn *sql.DB, driver string) error {
	// Use DB-agnostic SQL where possible.
	// SQLite uses AUTOINCREMENT, Postgres uses SERIAL.
	idType := "INTEGER PRIMARY KEY AUTOINCREMENT"
	nowDefault := "DEFAULT CURRENT_TIMESTAMP"
	boolType := "INTEGER"
	boolFalse := "DEFAULT 0"
	boolTrue := "DEFAULT 1"

	if driver == "postgres" {
		idType = "SERIAL PRIMARY KEY"
		nowDefault = "DEFAULT NOW()"
		boolType = "BOOLEAN"
		boolFalse = "DEFAULT FALSE"
		boolTrue = "DEFAULT TRUE"
	}

	stmts := []string{
		`CREATE TABLE IF NOT EXISTS users (
			id            ` + idType + `,
			username      TEXT NOT NULL UNIQUE,
			email         TEXT NOT NULL DEFAULT '',
			password_hash TEXT NOT NULL,
			created_at    TEXT NOT NULL ` + nowDefault + `
		);`,
		`CREATE TABLE IF NOT EXISTS categories (
			id          ` + idType + `,
			name        TEXT NOT NULL UNIQUE,
			description TEXT,
			created_at  TEXT NOT NULL ` + nowDefault + `,
			updated_at  TEXT NOT NULL ` + nowDefault + `
		);`,
		`CREATE TABLE IF NOT EXISTS items (
			id            ` + idType + `,
			name          TEXT NOT NULL,
			description   TEXT,
			is_completed  ` + boolType + ` NOT NULL ` + boolFalse + `,
			category_id   INTEGER REFERENCES categories(id) ON DELETE SET NULL,
			created_at    TEXT NOT NULL ` + nowDefault + `,
			updated_at    TEXT NOT NULL ` + nowDefault + `
		);`,
		`CREATE TABLE IF NOT EXISTS react_state (
			id          ` + idType + `,
			user_id     INTEGER NOT NULL,
			state_key   TEXT NOT NULL,
			state_value TEXT NOT NULL,
			updated_at  TEXT NOT NULL ` + nowDefault + `,
			UNIQUE(user_id, state_key),
			FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
		);`,
		`CREATE TABLE IF NOT EXISTS catalog_items (
			id          ` + idType + `,
			name        TEXT NOT NULL,
			description TEXT DEFAULT '',
			price       REAL NOT NULL DEFAULT 0.0,
			category    TEXT DEFAULT '',
			available   ` + boolType + ` ` + boolTrue + `,
			created_at  TEXT NOT NULL ` + nowDefault + `,
			updated_at  TEXT NOT NULL ` + nowDefault + `
		);`,
		`CREATE TABLE IF NOT EXISTS orders (
			id            ` + idType + `,
			user_id       INTEGER NOT NULL,
			status        TEXT NOT NULL DEFAULT 'draft',
			created_at    TEXT NOT NULL ` + nowDefault + `,
			submitted_at  TEXT,
			wait_minutes  INTEGER,
			feedback      TEXT,
			FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
		);`,
		`CREATE TABLE IF NOT EXISTS order_lines (
			id              ` + idType + `,
			order_id        INTEGER NOT NULL,
			catalog_item_id INTEGER NOT NULL,
			quantity        INTEGER NOT NULL DEFAULT 1,
			unit_price      TEXT NOT NULL DEFAULT '0.00',
			FOREIGN KEY (order_id)        REFERENCES orders(id)        ON DELETE CASCADE,
			FOREIGN KEY (catalog_item_id) REFERENCES catalog_items(id) ON DELETE CASCADE
		);`,
		`CREATE TABLE IF NOT EXISTS order_addresses (
			id       ` + idType + `,
			order_id INTEGER NOT NULL UNIQUE,
			street   TEXT NOT NULL DEFAULT '',
			city     TEXT NOT NULL DEFAULT '',
			zip_code TEXT NOT NULL DEFAULT '',
			phone    TEXT,
			notes    TEXT,
			FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
		);`,
	}
	for _, q := range stmts {
		if _, err := conn.Exec(q); err != nil {
			return err
		}
	}
	return nil
}
