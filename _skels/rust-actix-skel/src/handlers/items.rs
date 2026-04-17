//! `/api/items` CRUD — wrapper-shared resource the React frontend
//! consumes via `${BACKEND_URL}/api/items`.
//!
//! Schema mirrors django-bolt's `Item` model (table `items`) so the
//! shared `_shared/db.sqlite3` is fully interchangeable between the
//! two backends. Items carry an optional `category_id` FK to the
//! `categories` table (ON DELETE SET NULL). Every endpoint requires a
//! Bearer JWT — anonymous requests get 401 from the `AuthUser`
//! extractor.

use actix_web::{get, post, web, HttpResponse};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sqlx::sqlite::SqlitePool;

use crate::auth::AuthUser;
use crate::error::ApiError;

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

#[get("")]
pub async fn list_items(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items ORDER BY created_at DESC, id DESC",
    )
    .fetch_all(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_item(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    payload: web::Json<CreateItemPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation("item name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO items (name, description, is_completed, category_id, created_at, updated_at) \
         VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
    )
    .bind(&p.name)
    .bind(&p.description)
    .bind(p.is_completed)
    .bind(p.category_id)
    .bind(&now)
    .bind(&now)
    .fetch_one(pool.get_ref())
    .await?;
    let id = row.0;
    let item = ItemRow {
        id,
        name: p.name,
        description: p.description,
        is_completed: p.is_completed,
        category_id: p.category_id,
        created_at: now.clone(),
        updated_at: now,
    };
    Ok(HttpResponse::Created().json(item))
}

#[get("/{id}")]
pub async fn get_item(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(pool.get_ref())
    .await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;
    Ok(HttpResponse::Ok().json(item))
}

/// `POST /api/items/{id}/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent: completing an already-
/// completed item is a no-op that still returns 200.
#[post("/{id}/complete")]
pub async fn complete_item(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let now = utc_iso8601();
    let res = sqlx::query("UPDATE items SET is_completed = 1, updated_at = ? WHERE id = ?")
        .bind(&now)
        .bind(id)
        .execute(pool.get_ref())
        .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("item {id} not found")));
    }
    let row = sqlx::query_as::<_, ItemRow>(
        "SELECT id, name, description, is_completed, category_id, created_at, updated_at \
         FROM items WHERE id = ?",
    )
    .bind(id)
    .fetch_one(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(row))
}

fn utc_iso8601() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string()
}
