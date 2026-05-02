//! Sentinel-style domain error type.
//!
//! Every service returns `Result<_, DomainError>` and the HTTP layer
//! translates these variants into status codes via the `ResponseError`
//! impl below. Mirrors the FastAPI pilot's `core.errors` and the
//! Go skeleton's `shared.ErrNotFound / ErrConflict / …` sentinels.
//!
//! `From<sea_orm::DbErr>` lets repository adapters bubble database
//! errors up unchanged when they don't carry a domain meaning;
//! adapters convert recognisable failures (UNIQUE violation,
//! `RecordNotFound`, …) into the correct domain variant explicitly.

use actix_web::{http::StatusCode, HttpResponse, ResponseError};
use serde_json::json;
use thiserror::Error;

#[allow(dead_code)]
#[derive(Debug, Error)]
pub enum DomainError {
    /// Resource lookup miss. 404.
    #[error("not found: {0}")]
    NotFound(String),

    /// Uniqueness / state conflict (e.g. duplicate username on
    /// register). 409.
    #[error("conflict: {0}")]
    Conflict(String),

    /// Validation failed on a service-layer invariant. 400.
    #[error("validation: {0}")]
    Validation(String),

    /// Caller is not authenticated or the token was invalid. 401.
    #[error("unauthorized: {0}")]
    Unauthorized(String),

    /// Caller is authenticated but not allowed. 403.
    #[error("forbidden: {0}")]
    Forbidden(String),

    /// Database error — surfaced as 500 with the original message.
    #[error("database error: {0}")]
    Db(#[from] sea_orm::DbErr),

    /// JWT mint / verify error. 401 — never leak the reason.
    #[error("jwt: {0}")]
    Jwt(#[from] jsonwebtoken::errors::Error),

    /// Password hashing / verification error. 500.
    #[error("password: {0}")]
    Password(String),

    /// Catch-all 500 for everything else (uses anyhow internally so
    /// callers can attach context with `?` + `anyhow::Context`).
    #[error("internal: {0}")]
    Other(String),
}

impl DomainError {
    /// Convenience helper for adapters that want to wrap an
    /// `anyhow::Error`-style payload.
    #[allow(dead_code)]
    pub fn other<E: std::fmt::Display>(err: E) -> Self {
        DomainError::Other(err.to_string())
    }
}

impl ResponseError for DomainError {
    fn status_code(&self) -> StatusCode {
        match self {
            DomainError::NotFound(_) => StatusCode::NOT_FOUND,
            DomainError::Conflict(_) => StatusCode::CONFLICT,
            DomainError::Validation(_) => StatusCode::BAD_REQUEST,
            DomainError::Unauthorized(_) | DomainError::Jwt(_) => StatusCode::UNAUTHORIZED,
            DomainError::Forbidden(_) => StatusCode::FORBIDDEN,
            DomainError::Db(_) | DomainError::Password(_) | DomainError::Other(_) => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
        }
    }

    fn error_response(&self) -> HttpResponse {
        let status = self.status_code();
        let body = json!({
            "detail": self.to_string(),
            "status": status.as_u16(),
        });
        HttpResponse::build(status).json(body)
    }
}

/// Detect a UNIQUE-constraint violation across SQLite + Postgres
/// without depending on driver-specific error types. Adapters use
/// this to translate raw SeaORM errors into `DomainError::Conflict`.
pub fn is_unique_violation(err: &sea_orm::DbErr) -> bool {
    use sea_orm::{DbErr, RuntimeErr};
    let msg = match err {
        DbErr::Query(RuntimeErr::SqlxError(sqlx_err)) => sqlx_err.to_string(),
        DbErr::Exec(RuntimeErr::SqlxError(sqlx_err)) => sqlx_err.to_string(),
        other => other.to_string(),
    };
    msg.contains("UNIQUE constraint failed")
        || msg.contains("duplicate key value")
        || msg.contains("violates unique constraint")
}
