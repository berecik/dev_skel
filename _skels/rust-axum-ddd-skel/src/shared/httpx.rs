//! HTTP helpers reused by every resource's `routes.rs`.
//!
//! `ApiError` is the axum-level error wrapper — it implements
//! `IntoResponse` so handlers can `?`-propagate `DomainError` (via the
//! `From<DomainError>` impl below) and have the variant translated
//! into the correct status code + JSON body.
//!
//! The on-the-wire shape is `{ "detail": "<msg>", "status": <code> }`
//! — the canonical envelope every dev_skel backend honours.

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

use super::errors::DomainError;

/// Axum-friendly wrapper around `DomainError`. Handlers return
/// `Result<Json<T>, ApiError>` and let `?` translate domain failures
/// into HTTP responses.
#[derive(Debug)]
pub struct ApiError(pub DomainError);

impl ApiError {
    pub fn status_code(&self) -> StatusCode {
        match &self.0 {
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
}

impl From<DomainError> for ApiError {
    fn from(value: DomainError) -> Self {
        ApiError(value)
    }
}

impl From<sea_orm::DbErr> for ApiError {
    fn from(value: sea_orm::DbErr) -> Self {
        ApiError(DomainError::Db(value))
    }
}

impl From<jsonwebtoken::errors::Error> for ApiError {
    fn from(value: jsonwebtoken::errors::Error) -> Self {
        ApiError(DomainError::Jwt(value))
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = self.status_code();
        let detail = self.0.to_string();
        let body = Json(json!({
            "detail": detail,
            "status": status.as_u16(),
        }));
        (status, body).into_response()
    }
}

/// Build the canonical `{detail, status}` error envelope. Use this
/// when you want to short-circuit a handler without going through
/// `DomainError` (e.g. to short-circuit body parsing failures).
#[allow(dead_code)]
pub fn error_response(status: StatusCode, detail: impl Into<String>) -> Response {
    let body = Json(json!({
        "detail": detail.into(),
        "status": status.as_u16(),
    }));
    (status, body).into_response()
}
