//! Service-layer logic for the unauthenticated `/api/auth/{register,
//! login}` endpoints. Mirrors `_skels/rust-actix-ddd-skel/src/auth/service.rs`.
//!
//! Talks to `users::UserRepository` for persistence and to the JWT
//! mint helpers for token issuance. The service never holds a
//! `DatabaseConnection`.

use std::sync::Arc;

use chrono::Utc;

use crate::auth::jwt::{mint_access_token, mint_refresh_token};
use crate::auth::password::{hash_password, verify_password};
use crate::config::Config;
use crate::shared::DomainError;
use crate::users::repository::{NewUser, User};
use crate::users::UserRepository;

/// Input shape for `register` (mirrors the wrapper-shared
/// `/api/auth/register` contract).
#[derive(Debug, Clone)]
pub struct RegisterDTO {
    pub username: String,
    pub email: String,
    pub password: String,
    pub password_confirm: Option<String>,
}

/// Input shape for `login`. `username_or_email` may be either; we
/// branch on the presence of `@`.
#[derive(Debug, Clone)]
pub struct LoginDTO {
    pub username_or_email: String,
    pub password: String,
}

/// Result returned by `register` + `login`.
#[derive(Debug, Clone)]
pub struct AuthResult {
    pub user: User,
    pub access: String,
    pub refresh: String,
}

/// Coordinates user creation + credential checks. Holds an `Arc<dyn
/// UserRepository>` and a snapshot of `Config` for JWT signing.
#[derive(Clone)]
pub struct AuthService {
    cfg: Config,
    users: Arc<dyn UserRepository>,
}

impl AuthService {
    pub fn new(cfg: Config, users: Arc<dyn UserRepository>) -> Self {
        Self { cfg, users }
    }

    /// Create a fresh user (rejecting duplicates), hash the password,
    /// and mint an access + refresh token pair.
    pub async fn register(&self, dto: RegisterDTO) -> Result<AuthResult, DomainError> {
        if dto.username.trim().is_empty() {
            return Err(DomainError::Validation(
                "username cannot be empty".to_string(),
            ));
        }
        if dto.password.len() < 6 {
            return Err(DomainError::Validation(
                "password must be at least 6 characters".to_string(),
            ));
        }
        if let Some(confirm) = dto.password_confirm.as_deref() {
            if confirm != dto.password {
                return Err(DomainError::Validation(
                    "password and password_confirm do not match".to_string(),
                ));
            }
        }

        // Reject duplicate usernames with 409 (matches the contract
        // every other dev_skel backend honours).
        match self.users.get_by_username(&dto.username).await {
            Ok(_) => {
                return Err(DomainError::Conflict(format!(
                    "user '{}' already exists",
                    dto.username
                )));
            }
            Err(DomainError::NotFound(_)) => {}
            Err(other) => return Err(other),
        }

        let hash = hash_password(&dto.password)?;
        let user = self
            .users
            .create(NewUser {
                username: dto.username.clone(),
                email: dto.email.clone(),
                password_hash: hash,
                created_at: Utc::now(),
            })
            .await?;

        let access = mint_access_token(user.id as i64, &self.cfg)?;
        let refresh = mint_refresh_token(user.id as i64, &self.cfg)?;
        Ok(AuthResult {
            user,
            access,
            refresh,
        })
    }

    /// Validate the supplied credentials and return a fresh token
    /// pair. Always returns `DomainError::Unauthorized` on failure
    /// so the caller never leaks which field was wrong.
    pub async fn login(&self, dto: LoginDTO) -> Result<AuthResult, DomainError> {
        if dto.username_or_email.is_empty() || dto.password.is_empty() {
            return Err(DomainError::Unauthorized(
                "invalid username or password".to_string(),
            ));
        }

        let lookup = if dto.username_or_email.contains('@') {
            self.users.get_by_email(&dto.username_or_email).await
        } else {
            self.users.get_by_username(&dto.username_or_email).await
        };
        let user = match lookup {
            Ok(u) => u,
            Err(DomainError::NotFound(_)) => {
                return Err(DomainError::Unauthorized(
                    "invalid username or password".to_string(),
                ));
            }
            Err(other) => return Err(other),
        };

        if !verify_password(&dto.password, &user.password_hash)? {
            return Err(DomainError::Unauthorized(
                "invalid username or password".to_string(),
            ));
        }

        let access = mint_access_token(user.id as i64, &self.cfg)?;
        let refresh = mint_refresh_token(user.id as i64, &self.cfg)?;
        Ok(AuthResult {
            user,
            access,
            refresh,
        })
    }
}
