//! Seed default user accounts from environment variables at startup.
//!
//! Reads two sets of env vars:
//!
//! * `USER_LOGIN`, `USER_EMAIL`, `USER_PASSWORD` — regular user
//! * `SUPERUSER_LOGIN`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD` — admin
//!
//! If all three vars of a set are present **and** no row with that
//! username already exists, the account is inserted with an argon2-hashed
//! password. Existing accounts are silently skipped so the function is
//! idempotent and safe to call on every startup.

use sqlx::SqlitePool;
use std::env;

use crate::auth::hash_password;

/// Seed default accounts from env vars. Call once after schema bootstrap.
pub async fn seed_default_accounts(pool: &SqlitePool) {
    seed_account(pool, "USER_LOGIN", "USER_EMAIL", "USER_PASSWORD").await;
    seed_account(pool, "SUPERUSER_LOGIN", "SUPERUSER_EMAIL", "SUPERUSER_PASSWORD").await;
}

async fn seed_account(pool: &SqlitePool, login_var: &str, email_var: &str, password_var: &str) {
    let login = match env::var(login_var) {
        Ok(v) if !v.is_empty() => v,
        _ => return,
    };
    let email = match env::var(email_var) {
        Ok(v) if !v.is_empty() => v,
        _ => return,
    };
    let password = match env::var(password_var) {
        Ok(v) if !v.is_empty() => v,
        _ => return,
    };

    // Skip if user already exists.
    let existing: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE username = ?")
        .bind(&login)
        .fetch_optional(pool)
        .await
        .unwrap_or(None);
    if existing.is_some() {
        tracing::info!(username = %login, "seed: account already exists, skipping");
        return;
    }

    let password_hash = match hash_password(&password) {
        Ok(h) => h,
        Err(e) => {
            tracing::error!(error = ?e, username = %login, "seed: failed to hash password");
            return;
        }
    };

    match sqlx::query("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)")
        .bind(&login)
        .bind(&email)
        .bind(&password_hash)
        .execute(pool)
        .await
    {
        Ok(_) => tracing::info!(username = %login, email = %email, "seed: created default account"),
        Err(e) => tracing::error!(error = ?e, username = %login, "seed: failed to insert account"),
    }
}
