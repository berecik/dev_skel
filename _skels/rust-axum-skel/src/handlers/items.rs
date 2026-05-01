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
use sea_orm::{ActiveModelTrait, EntityTrait, QueryOrder, Set};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::item;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct CreateItemPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub is_completed: bool,
    #[serde(default)]
    pub category_id: Option<i32>,
}

pub async fn list_items(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = item::Entity::find()
        .order_by_desc(item::Column::CreatedAt)
        .order_by_desc(item::Column::Id)
        .all(&state.db)
        .await?;
    Ok(Json(rows))
}

pub async fn create_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CreateItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "item name cannot be empty".to_string(),
        ));
    }
    let now = Utc::now();
    let new_item = item::ActiveModel {
        name: Set(payload.name),
        description: Set(payload.description),
        is_completed: Set(payload.is_completed),
        category_id: Set(payload.category_id),
        created_at: Set(now),
        updated_at: Set(now),
        ..Default::default()
    };
    let inserted = new_item.insert(&state.db).await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn get_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = item::Entity::find_by_id(id).one(&state.db).await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;
    Ok(Json(item))
}

/// `POST /api/items/:id/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent: completing an already-
/// completed item is a no-op that still returns 200.
pub async fn complete_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = item::Entity::find_by_id(id).one(&state.db).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;

    let mut active: item::ActiveModel = existing.into();
    active.is_completed = Set(true);
    active.updated_at = Set(Utc::now());
    let updated = active.update(&state.db).await?;
    Ok(Json(updated))
}
