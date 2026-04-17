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
use serde::{Deserialize, Serialize};

use crate::auth::AuthUser;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct CategoryRow {
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct CreateCategoryPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

pub async fn list_categories(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
) -> Result<Json<Vec<CategoryRow>>, ApiError> {
    let rows = sqlx::query_as::<_, CategoryRow>(
        "SELECT id, name, description, created_at, updated_at \
         FROM categories ORDER BY name ASC",
    )
    .fetch_all(&state.pool)
    .await?;
    Ok(Json(rows))
}

pub async fn create_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation("category name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO categories (name, description, created_at, updated_at) \
         VALUES (?, ?, ?, ?) RETURNING id",
    )
    .bind(&payload.name)
    .bind(&payload.description)
    .bind(&now)
    .bind(&now)
    .fetch_one(&state.pool)
    .await
    .map_err(|e| {
        // Map UNIQUE constraint violation to a 409 Conflict.
        if let sqlx::Error::Database(ref db_err) = e {
            if db_err.message().contains("UNIQUE") {
                return ApiError::Conflict(format!("category '{}' already exists", payload.name));
            }
        }
        ApiError::Database(e)
    })?;
    let id = row.0;
    let category = CategoryRow {
        id,
        name: payload.name,
        description: payload.description,
        created_at: now.clone(),
        updated_at: now,
    };
    Ok((StatusCode::CREATED, Json(category)))
}

pub async fn get_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i64>,
) -> Result<Json<CategoryRow>, ApiError> {
    let row = sqlx::query_as::<_, CategoryRow>(
        "SELECT id, name, description, created_at, updated_at \
         FROM categories WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(&state.pool)
    .await?;
    let category = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    Ok(Json(category))
}

pub async fn update_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i64>,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<Json<CategoryRow>, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation("category name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let res = sqlx::query(
        "UPDATE categories SET name = ?, description = ?, updated_at = ? WHERE id = ?",
    )
    .bind(&payload.name)
    .bind(&payload.description)
    .bind(&now)
    .bind(id)
    .execute(&state.pool)
    .await
    .map_err(|e| {
        if let sqlx::Error::Database(ref db_err) = e {
            if db_err.message().contains("UNIQUE") {
                return ApiError::Conflict(format!("category '{}' already exists", payload.name));
            }
        }
        ApiError::Database(e)
    })?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("category {id} not found")));
    }
    let row = sqlx::query_as::<_, CategoryRow>(
        "SELECT id, name, description, created_at, updated_at \
         FROM categories WHERE id = ?",
    )
    .bind(id)
    .fetch_one(&state.pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete_category(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(id): Path<i64>,
) -> Result<impl IntoResponse, ApiError> {
    let res = sqlx::query("DELETE FROM categories WHERE id = ?")
        .bind(id)
        .execute(&state.pool)
        .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("category {id} not found")));
    }
    Ok(StatusCode::NO_CONTENT)
}

fn utc_iso8601() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string()
}
