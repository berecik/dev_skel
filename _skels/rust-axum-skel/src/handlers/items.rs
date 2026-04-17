//! `/api/items` CRUD — wrapper-shared resource the React frontend
//! consumes via `${BACKEND_URL}/api/items`.
//!
//! Schema mirrors django-bolt's `Item` model (table `items`) so the
//! shared `_shared/db.sqlite3` is fully interchangeable between the
//! two backends. Items carry an optional `category_id` FK to the
//! `categories` table (ON DELETE SET NULL). Every endpoint requires a
//! Bearer JWT — anonymous requests get 401 from the `AuthUser`
//! extractor.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};

use crate::auth::AuthUser;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct ItemRow {
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub is_completed: bool,
    pub category_id: Option<i64>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct CreateItemPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub is_completed: bool,
    #[serde(default)]
    pub category_id: Option<i64>,
}

pub async fn list_items(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
) -> Result<Json<Vec<ItemRow>>, ApiError> {
    let rows = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items ORDER BY created_at DESC, id DESC",
    )
    .fetch_all(&state.pool)
    .await?;
    Ok(Json(rows))
}

pub async fn create_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CreateItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation("item name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO items (name, description, is_completed, category_id, created_at, updated_at) \
         VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
    )
    .bind(&payload.name)
    .bind(&payload.description)
    .bind(payload.is_completed)
    .bind(payload.category_id)
    .bind(&now)
    .bind(&now)
    .fetch_one(&state.pool)
    .await?;
    let id = row.0;
    let item = ItemRow {
        id,
        name: payload.name,
        description: payload.description,
        is_completed: payload.is_completed,
        category_id: payload.category_id,
        created_at: now.clone(),
        updated_at: now,
    };
    Ok((StatusCode::CREATED, Json(item)))
}

pub async fn get_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i64>,
) -> Result<Json<ItemRow>, ApiError> {
    let row = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(&state.pool)
    .await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;
    Ok(Json(item))
}

/// `POST /api/items/:id/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent: completing an already-
/// completed item is a no-op that still returns 200.
pub async fn complete_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i64>,
) -> Result<Json<ItemRow>, ApiError> {
    let now = utc_iso8601();
    let res = sqlx::query("UPDATE items SET is_completed = 1, updated_at = ? WHERE id = ?")
        .bind(&now)
        .bind(id)
        .execute(&state.pool)
        .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("item {id} not found")));
    }
    let row = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items WHERE id = ?",
    )
    .bind(id)
    .fetch_one(&state.pool)
    .await?;
    Ok(Json(row))
}

fn utc_iso8601() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string()
}
