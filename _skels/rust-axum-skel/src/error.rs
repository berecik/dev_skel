//! Common error type for handlers.
//!
//! Every handler returns `Result<Json<T>, ApiError>` so the
//! `IntoResponse` impl translates failure modes to a JSON body the
//! React frontend already knows how to handle (`AuthError` for 401/403,
//! generic `Error("HTTP {status}: {body}")` for everything else).

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ApiError {
    /// Validation failed on the request body. 400.
    #[error("validation: {0}")]
    Validation(String),

    /// The caller did not provide a JWT or the JWT was invalid /
    /// expired. 401.
    #[error("unauthorized: {0}")]
    Unauthorized(String),

    /// The resource was not found. 404.
    #[error("not found: {0}")]
    NotFound(String),

    /// Resource conflict (e.g. duplicate username on register). 409.
    #[error("conflict: {0}")]
    Conflict(String),

    /// Database error — surfaced as 500.
    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),

    /// JWT mint / verify error.
    #[error("jwt: {0}")]
    Jwt(#[from] jsonwebtoken::errors::Error),

    /// Password hashing / verification error.
    #[error("password: {0}")]
    Password(String),

    /// Catch-all 500.
    #[error("internal: {0}")]
    Internal(String),
}

impl ApiError {
    pub fn status_code(&self) -> StatusCode {
        match self {
            ApiError::Validation(_) => StatusCode::BAD_REQUEST,
            ApiError::Unauthorized(_) | ApiError::Jwt(_) => StatusCode::UNAUTHORIZED,
            ApiError::NotFound(_) => StatusCode::NOT_FOUND,
            ApiError::Conflict(_) => StatusCode::CONFLICT,
            ApiError::Database(_) | ApiError::Password(_) | ApiError::Internal(_) => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = self.status_code();
        let detail = self.to_string();
        let body = Json(json!({
            "detail": detail,
            "status": status.as_u16(),
        }));
        (status, body).into_response()
    }
}
