//! SQLite connection pool + schema bootstrap.
//!
//! The wrapper-shared `_shared/db.sqlite3` file is the canonical
//! storage location (resolved via `Config::database_url`). On first
//! connect we create the `users`, `items`, and `react_state` tables
//! `IF NOT EXISTS` so a freshly-generated wrapper boots with no
//! migrations step required. The schema mirrors the django-bolt skel's
//! `app/models.py` so a single `_shared/db.sqlite3` can be read by
//! either backend without translation.

use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};

/// Connect to the database at `database_url` and run idempotent schema
/// creation. Returns the connection pool the handlers share via the
/// router state.
pub async fn connect_and_init(database_url: &str) -> Result<SqlitePool, sqlx::Error> {
    let pool = SqlitePoolOptions::new()
        .max_connections(8)
        .connect(database_url)
        .await?;
    init_schema(&pool).await?;
    Ok(pool)
}

/// Create the wrapper-shared tables if they do not exist yet.
///
/// Schemas:
/// * `users` — id PK, username unique, email, password_hash (argon2),
///   created_at.
/// * `items` — wrapper-shared CRUD resource the React frontend
///   consumes via `${BACKEND_URL}/api/items`. Mirrors django-bolt's
///   `Item` model field layout (intentionally unscoped — every user
///   sees every item — so cross-stack tests stay simple).
/// * `react_state` — per-user JSON key/value store backing the
///   `useAppState<T>(key, default)` React hook.
async fn init_schema(pool: &SqlitePool) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            email         TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );
        "#,
    )
    .execute(pool)
    .await?;

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            description   TEXT,
            is_completed  INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );
        "#,
    )
    .execute(pool)
    .await?;

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS react_state (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            UNIQUE(user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        "#,
    )
    .execute(pool)
    .await?;

    Ok(())
}
