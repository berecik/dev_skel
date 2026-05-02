//! HTTP helpers reused by every resource's `routes.rs`.
//!
//! The actix-web `DomainError -> HttpResponse` mapping is implemented
//! by the `ResponseError` impl on `shared::errors::DomainError`, so
//! handlers can simply `?` repo / service results. This module exposes
//! a small extra envelope helper for the cases where a route wants to
//! emit a JSON error directly (e.g. malformed body parsing) without
//! constructing a `DomainError`.

use actix_web::{http::StatusCode, HttpResponse};
use serde_json::json;

/// Build the canonical `{detail, status}` error envelope every dev_skel
/// backend honours. Use this when you want to short-circuit a handler
/// without going through `DomainError`.
#[allow(dead_code)]
pub fn error_response(status: StatusCode, detail: impl Into<String>) -> HttpResponse {
    HttpResponse::build(status).json(json!({
        "detail": detail.into(),
        "status": status.as_u16(),
    }))
}
