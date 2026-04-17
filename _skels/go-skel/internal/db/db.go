// Package db opens the SQLite (or other JDBC-style) connection and
// runs idempotent CREATE TABLE IF NOT EXISTS for the wrapper-shared
// `users`, `categories`, `items`, and `react_state` tables. Schema
// mirrors the django-bolt skeleton's `app/models.py` so a single
// `_shared/db.sqlite3` is interchangeable across every dev_skel
// backend.
package db

import (
	"database/sql"

	_ "modernc.org/sqlite" // registers the "sqlite" driver
)

// Open returns a *sql.DB after running the schema bootstrap.
// `path` is the resolved file path (config.normalizeSQLiteURL has
// already stripped any `sqlite:` prefix).
func Open(path string) (*sql.DB, error) {
	conn, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	// modernc.org/sqlite recommends a single connection for SQLite
	// because the underlying driver serialises writes anyway. Setting
	// MaxOpenConns to 1 also avoids `database is locked` flakes
	// during the cross-stack test which fires concurrent requests.
	conn.SetMaxOpenConns(1)
	// Enable foreign key enforcement — SQLite defaults to OFF.
	if _, err := conn.Exec("PRAGMA foreign_keys = ON"); err != nil {
		_ = conn.Close()
		return nil, err
	}
	if err := initSchema(conn); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return conn, nil
}

func initSchema(conn *sql.DB) error {
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS users (
			id            INTEGER PRIMARY KEY AUTOINCREMENT,
			username      TEXT NOT NULL UNIQUE,
			email         TEXT NOT NULL DEFAULT '',
			password_hash TEXT NOT NULL,
			created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
		);`,
		`CREATE TABLE IF NOT EXISTS categories (
			id          INTEGER PRIMARY KEY AUTOINCREMENT,
			name        TEXT NOT NULL UNIQUE,
			description TEXT,
			created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
		);`,
		`CREATE TABLE IF NOT EXISTS items (
			id            INTEGER PRIMARY KEY AUTOINCREMENT,
			name          TEXT NOT NULL,
			description   TEXT,
			is_completed  INTEGER NOT NULL DEFAULT 0,
			category_id   INTEGER REFERENCES categories(id) ON DELETE SET NULL,
			created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
		);`,
		`CREATE TABLE IF NOT EXISTS react_state (
			id          INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id     INTEGER NOT NULL,
			state_key   TEXT NOT NULL,
			state_value TEXT NOT NULL,
			updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(user_id, state_key),
			FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
		);`,
	}
	for _, q := range stmts {
		if _, err := conn.Exec(q); err != nil {
			return err
		}
	}
	return nil
}
