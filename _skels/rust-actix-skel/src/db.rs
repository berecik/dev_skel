//! SQLite connection pool + schema bootstrap.
//!
//! The wrapper-shared `_shared/db.sqlite3` file is the canonical
//! storage location (resolved via `Config::database_url`). On first
//! connect we create the `users`, `categories`, `items`,
//! `react_state`, `catalog_items`, `orders`, `order_lines`, and
//! `order_addresses` tables `IF NOT EXISTS` so a freshly-generated
//! wrapper boots with no migrations step required. The schema mirrors
//! the django-bolt skel's `app/models.py` so a single
//! `_shared/db.sqlite3` can be read by either backend without
//! translation.

use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};

/// Connect to the database at `database_url` and run idempotent schema
/// creation. Returns the connection pool the handlers share via
/// `web::Data`.
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
/// * `categories` — wrapper-shared category resource. Items may
///   optionally reference a category via `category_id`.
/// * `items` — wrapper-shared CRUD resource the React frontend
///   consumes via `${BACKEND_URL}/api/items`. Mirrors django-bolt's
///   `Item` model field layout (intentionally unscoped — every user
///   sees every item — so cross-stack tests stay simple). Carries an
///   optional `category_id` FK to `categories`.
/// * `react_state` — per-user JSON key/value store backing the
///   `useAppState<T>(key, default)` React hook.
/// * `catalog_items` — purchasable items with name, price, category,
///   and availability flag.
/// * `orders` — per-user orders with status lifecycle (draft →
///   submitted → approved / rejected).
/// * `order_lines` — line items linking an order to catalog items
///   with quantity and unit price.
/// * `order_addresses` — one-to-one delivery address per order.
async fn init_schema(pool: &SqlitePool) -> Result<(), sqlx::Error> {
    // Enable foreign key enforcement — SQLite has it off by default.
    sqlx::query("PRAGMA foreign_keys = ON;")
        .execute(pool)
        .await?;

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
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
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
            category_id   INTEGER REFERENCES categories(id) ON DELETE SET NULL,
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

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS catalog_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            price       REAL NOT NULL,
            category    TEXT DEFAULT '',
            available   INTEGER DEFAULT 1
        );
        "#,
    )
    .execute(pool)
    .await?;

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            status       TEXT DEFAULT 'draft',
            created_at   TEXT DEFAULT (datetime('now')),
            submitted_at TEXT,
            wait_minutes INTEGER,
            feedback     TEXT
        );
        "#,
    )
    .execute(pool)
    .await?;

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS order_lines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        INTEGER NOT NULL REFERENCES orders(id),
            catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
            quantity        INTEGER DEFAULT 1,
            unit_price      REAL DEFAULT 0.0
        );
        "#,
    )
    .execute(pool)
    .await?;

    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS order_addresses (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
            street   TEXT NOT NULL,
            city     TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            phone    TEXT DEFAULT '',
            notes    TEXT DEFAULT ''
        );
        "#,
    )
    .execute(pool)
    .await?;

    Ok(())
}
