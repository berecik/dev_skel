//! Seed default user accounts from environment variables at startup.
//!
//! Reads `USER_LOGIN`, `USER_EMAIL`, `USER_PASSWORD` and
//! `SUPERUSER_LOGIN`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD` from the
//! process environment and inserts each account into the `users` table
//! when one with that username does not already exist.

use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, Set,
};

use crate::auth::hash_password;
use crate::entities::user;
use crate::error::ApiError;

/// Account descriptor read from env vars.
struct SeedAccount {
    username: String,
    email: String,
    password: String,
}

/// Seed default accounts (regular user + superuser) into the database.
///
/// Each account is only created when the username does not already exist,
/// making the function safe to call on every startup.
pub async fn seed_default_accounts(db: &DatabaseConnection) -> Result<(), ApiError> {
    let accounts = collect_accounts();

    for acct in &accounts {
        if acct.username.is_empty() || acct.password.is_empty() {
            continue;
        }

        let existing = user::Entity::find()
            .filter(user::Column::Username.eq(&acct.username))
            .one(db)
            .await?;

        if existing.is_some() {
            tracing::info!(
                target: "rust_axum_skel",
                "[seed] User '{}' already exists — skipping",
                acct.username,
            );
            continue;
        }

        let hash = hash_password(&acct.password)?;
        let new_user = user::ActiveModel {
            username: Set(acct.username.clone()),
            email: Set(acct.email.clone()),
            password_hash: Set(hash),
            created_at: Set(Utc::now()),
            ..Default::default()
        };
        new_user.insert(db).await?;

        tracing::info!(
            target: "rust_axum_skel",
            "[seed] Created default user '{}'",
            acct.username,
        );
    }

    Ok(())
}

/// Collect seed accounts from environment variables.
fn collect_accounts() -> Vec<SeedAccount> {
    vec![
        SeedAccount {
            username: std::env::var("USER_LOGIN").unwrap_or_default(),
            email: std::env::var("USER_EMAIL").unwrap_or_default(),
            password: std::env::var("USER_PASSWORD").unwrap_or_default(),
        },
        SeedAccount {
            username: std::env::var("SUPERUSER_LOGIN").unwrap_or_default(),
            email: std::env::var("SUPERUSER_EMAIL").unwrap_or_default(),
            password: std::env::var("SUPERUSER_PASSWORD").unwrap_or_default(),
        },
    ]
}
