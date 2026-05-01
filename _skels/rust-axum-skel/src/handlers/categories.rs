//! `/api/categories` CRUD — wrapper-shared category resource.
//!
//! Categories provide optional grouping for items via the
//! `items.category_id` FK. The schema mirrors the django-bolt skel's
//! `Category` model (table `categories`) so the shared
//! `_shared/db.sqlite3` is fully interchangeable between backends.
//! Every endpoint requires a Bearer JWT — anonymous requests get 401
//! from the `AuthUser` extractor.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use chrono::Utc;
use sea_orm::sea_query::OnConflict;
use sea_orm::{
    ActiveModelTrait, DbErr, EntityTrait, ModelTrait, QueryOrder, RuntimeErr, Set,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::category;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct CreateCategoryPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

pub async fn list_categories(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = category::Entity::find()
        .order_by_asc(category::Column::Name)
        .all(&state.db)
        .await?;
    Ok(Json(rows))
}

pub async fn create_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "category name cannot be empty".to_string(),
        ));
    }
    let now = Utc::now();
    let new_cat = category::ActiveModel {
        name: Set(payload.name.clone()),
        description: Set(payload.description),
        created_at: Set(now),
        updated_at: Set(now),
        ..Default::default()
    };
    let inserted = new_cat.insert(&state.db).await.map_err(|e| {
        if is_unique_violation(&e) {
            ApiError::Conflict(format!("category '{}' already exists", payload.name))
        } else {
            ApiError::Database(e)
        }
    })?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn get_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = category::Entity::find_by_id(id).one(&state.db).await?;
    let cat = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    Ok(Json(cat))
}

pub async fn update_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i32>,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "category name cannot be empty".to_string(),
        ));
    }
    let row = category::Entity::find_by_id(id).one(&state.db).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;

    let mut active: category::ActiveModel = existing.into();
    active.name = Set(payload.name.clone());
    active.description = Set(payload.description);
    active.updated_at = Set(Utc::now());
    let updated = active.update(&state.db).await.map_err(|e| {
        if is_unique_violation(&e) {
            ApiError::Conflict(format!("category '{}' already exists", payload.name))
        } else {
            ApiError::Database(e)
        }
    })?;
    Ok(Json(updated))
}

pub async fn delete_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = category::Entity::find_by_id(id).one(&state.db).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    existing.delete(&state.db).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// Detect a UNIQUE-constraint violation across SQLite and Postgres
/// without depending on driver-specific error types.
fn is_unique_violation(err: &DbErr) -> bool {
    let msg = match err {
        DbErr::Query(RuntimeErr::SqlxError(sqlx_err)) => sqlx_err.to_string(),
        DbErr::Exec(RuntimeErr::SqlxError(sqlx_err)) => sqlx_err.to_string(),
        other => other.to_string(),
    };
    msg.contains("UNIQUE constraint failed")
        || msg.contains("duplicate key value")
        || msg.contains("violates unique constraint")
}

// Tag the (currently-unused) `OnConflict` import so future SeaORM
// upserts can reach for it without a fresh `use` line.
#[allow(dead_code)]
fn _on_conflict_handle() -> OnConflict {
    OnConflict::new()
}
