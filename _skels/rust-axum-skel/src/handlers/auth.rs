//! `/api/auth/register` and `/api/auth/login` — JWT bearer auth.
//!
//! Response shapes match the contract every dev_skel backend honours
//! so the React frontend's `src/api/auth.ts` works against any of them
//! without a code change:
//!
//! * register → 201 `{ user: { id, username, email }, access, refresh }`
//! * login → 200 `{ access, refresh, user_id, username }`

use std::sync::Arc;

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::auth::{hash_password, mint_access_token, mint_refresh_token, verify_password};
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct RegisterPayload {
    pub username: String,
    pub email: String,
    pub password: String,
    /// Optional confirmation field — the React skel sends it; we accept
    /// it without it being required so other clients (curl, the smoke
    /// runner) can omit it.
    #[serde(default)]
    pub password_confirm: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoginPayload {
    pub username: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
struct UserOut {
    id: i64,
    username: String,
    email: String,
}

pub async fn register_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<RegisterPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.username.trim().is_empty() {
        return Err(ApiError::Validation("username cannot be empty".to_string()));
    }
    if payload.password.len() < 6 {
        return Err(ApiError::Validation(
            "password must be at least 6 characters".to_string(),
        ));
    }
    if let Some(confirm) = &payload.password_confirm {
        if confirm != &payload.password {
            return Err(ApiError::Validation(
                "password and password_confirm do not match".to_string(),
            ));
        }
    }

    let existing: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE username = ?")
        .bind(&payload.username)
        .fetch_optional(&state.pool)
        .await?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!(
            "user '{}' already exists",
            payload.username
        )));
    }

    let hash = hash_password(&payload.password)?;
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?) RETURNING id",
    )
    .bind(&payload.username)
    .bind(&payload.email)
    .bind(&hash)
    .fetch_one(&state.pool)
    .await?;
    let new_id = row.0;

    let access = mint_access_token(new_id, &state.config)?;
    let refresh = mint_refresh_token(new_id, &state.config)?;

    let body = Json(json!({
        "user": UserOut { id: new_id, username: payload.username.clone(), email: payload.email.clone() },
        "access": access,
        "refresh": refresh,
    }));
    Ok((StatusCode::CREATED, body))
}

pub async fn login_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<LoginPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let row: Option<(i64, String, String)> = sqlx::query_as(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
    )
    .bind(&payload.username)
    .fetch_optional(&state.pool)
    .await?;

    let (id, username, password_hash) = row.ok_or_else(|| {
        ApiError::Unauthorized("invalid username or password".to_string())
    })?;

    if !verify_password(&payload.password, &password_hash)? {
        return Err(ApiError::Unauthorized(
            "invalid username or password".to_string(),
        ));
    }

    let access = mint_access_token(id, &state.config)?;
    let refresh = mint_refresh_token(id, &state.config)?;

    let body = Json(json!({
        "access": access,
        "refresh": refresh,
        "user_id": id,
        "username": username,
    }));
    Ok((StatusCode::OK, body))
}
