//! Seed default user accounts from environment variables at startup.
//!
//! Reads `USER_LOGIN`, `USER_EMAIL`, `USER_PASSWORD` and
//! `SUPERUSER_LOGIN`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD` from
//! the process environment and inserts each account through the
//! `UserRepository` interface — so the seed flow never sees
//! `DatabaseConnection`.

use std::sync::Arc;

use chrono::Utc;

use crate::auth::password::hash_password;
use crate::shared::DomainError;
use crate::users::repository::NewUser;
use crate::users::UserRepository;

/// Account descriptor read from env vars.
struct SeedAccount {
    username: String,
    email: String,
    password: String,
}

/// Seed default accounts (regular user + superuser) into the
/// repository. Each account is only created when the username does
/// not already exist, making the function safe to call on every
/// startup.
pub async fn seed_default_accounts(
    users: Arc<dyn UserRepository>,
) -> Result<(), DomainError> {
    let accounts = collect_accounts();

    for acct in &accounts {
        if acct.username.is_empty() || acct.password.is_empty() {
            continue;
        }

        match users.get_by_username(&acct.username).await {
            Ok(_) => {
                tracing::info!(
                    target: "rust_axum_ddd_skel",
                    "[seed] User '{}' already exists - skipping",
                    acct.username,
                );
                continue;
            }
            Err(DomainError::NotFound(_)) => {}
            Err(other) => return Err(other),
        }

        let hash = hash_password(&acct.password)?;
        users
            .create(NewUser {
                username: acct.username.clone(),
                email: acct.email.clone(),
                password_hash: hash,
                created_at: Utc::now(),
            })
            .await?;

        tracing::info!(
            target: "rust_axum_ddd_skel",
            "[seed] Created default user '{}'",
            acct.username,
        );
    }

    Ok(())
}

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
