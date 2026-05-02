//! `/api/auth/{register, login}` HTTP handlers. Thin: parse → call
//! `AuthService` → translate domain errors into HTTP via the
//! `IntoResponse` impl on `ApiError`.

use std::sync::Arc;

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde::Deserialize;
use serde_json::json;

use crate::auth::service::{AuthService, LoginDTO, RegisterDTO};
use crate::shared::ApiError;

#[derive(Debug, Deserialize)]
pub struct RegisterPayload {
    pub username: String,
    pub email: String,
    pub password: String,
    /// Optional confirmation field — the React skel sends it; we
    /// accept it without it being required so other clients (curl,
    /// the smoke runner) can omit it.
    #[serde(default)]
    pub password_confirm: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoginPayload {
    pub username: String,
    pub password: String,
}

pub async fn register_handler(
    State(svc): State<Arc<AuthService>>,
    Json(payload): Json<RegisterPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let res = svc
        .register(RegisterDTO {
            username: payload.username,
            email: payload.email,
            password: payload.password,
            password_confirm: payload.password_confirm,
        })
        .await?;

    let body = Json(json!({
        "user": {
            "id": res.user.id,
            "username": res.user.username,
            "email": res.user.email,
        },
        "access": res.access,
        "refresh": res.refresh,
    }));
    Ok((StatusCode::CREATED, body))
}

pub async fn login_handler(
    State(svc): State<Arc<AuthService>>,
    Json(payload): Json<LoginPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let res = svc
        .login(LoginDTO {
            username_or_email: payload.username,
            password: payload.password,
        })
        .await?;

    let body = Json(json!({
        "access": res.access,
        "refresh": res.refresh,
        "user_id": res.user.id,
        "username": res.user.username,
    }));
    Ok((StatusCode::OK, body))
}
