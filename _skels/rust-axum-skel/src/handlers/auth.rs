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
use chrono::Utc;
use sea_orm::{ActiveModelTrait, ColumnTrait, EntityTrait, QueryFilter, Set};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::auth::{hash_password, mint_access_token, mint_refresh_token, verify_password};
use crate::entities::user;
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
    id: i32,
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

    // Reject duplicate usernames with 409 (matches the contract every
    // other dev_skel backend honours; the React frontend surfaces 4xx
    // errors to the user verbatim via fetch + AuthError).
    let existing = user::Entity::find()
        .filter(user::Column::Username.eq(&payload.username))
        .one(&state.db)
        .await?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!(
            "user '{}' already exists",
            payload.username
        )));
    }

    let hash = hash_password(&payload.password)?;
    let new_user = user::ActiveModel {
        username: Set(payload.username.clone()),
        email: Set(payload.email.clone()),
        password_hash: Set(hash),
        created_at: Set(Utc::now()),
        ..Default::default()
    };
    let inserted = new_user.insert(&state.db).await?;
    let new_id = inserted.id;

    let access = mint_access_token(new_id as i64, &state.config)?;
    let refresh = mint_refresh_token(new_id as i64, &state.config)?;

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
    let column_filter = if payload.username.contains('@') {
        user::Column::Email
    } else {
        user::Column::Username
    };
    let row = user::Entity::find()
        .filter(column_filter.eq(&payload.username))
        .one(&state.db)
        .await?;

    let user_row = row.ok_or_else(|| {
        ApiError::Unauthorized("invalid username or password".to_string())
    })?;

    if !verify_password(&payload.password, &user_row.password_hash)? {
        return Err(ApiError::Unauthorized(
            "invalid username or password".to_string(),
        ));
    }

    let access = mint_access_token(user_row.id as i64, &state.config)?;
    let refresh = mint_refresh_token(user_row.id as i64, &state.config)?;

    let body = Json(json!({
        "access": access,
        "refresh": refresh,
        "user_id": user_row.id,
        "username": user_row.username,
    }));
    Ok((StatusCode::OK, body))
}
