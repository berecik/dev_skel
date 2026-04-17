//! `/api/categories` CRUD — wrapper-shared category resource.
//!
//! Categories provide optional grouping for items via the
//! `items.category_id` FK. The schema mirrors the django-bolt skel's
//! `Category` model (table `categories`) so the shared
//! `_shared/db.sqlite3` is fully interchangeable between backends.
//! Every endpoint requires a Bearer JWT — anonymous requests get 401
//! from the `AuthUser` extractor.

use actix_web::{delete, get, post, put, web, HttpResponse};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sqlx::sqlite::SqlitePool;

use crate::auth::AuthUser;
use crate::error::ApiError;

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

#[get("")]
pub async fn list_categories(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = sqlx::query_as::<_, CategoryRow>(
        "SELECT id, name, description, created_at, updated_at \
         FROM categories ORDER BY name ASC",
    )
    .fetch_all(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_category(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation("category name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO categories (name, description, created_at, updated_at) \
         VALUES (?, ?, ?, ?) RETURNING id",
    )
    .bind(&p.name)
    .bind(&p.description)
    .bind(&now)
    .bind(&now)
    .fetch_one(pool.get_ref())
    .await
    .map_err(|e| {
        // Map UNIQUE constraint violation to a 409 Conflict.
        if let sqlx::Error::Database(ref db_err) = e {
            if db_err.message().contains("UNIQUE") {
                return ApiError::Conflict(format!("category '{}' already exists", p.name));
            }
        }
        ApiError::Database(e)
    })?;
    let id = row.0;
    let category = CategoryRow {
        id,
        name: p.name,
        description: p.description,
        created_at: now.clone(),
        updated_at: now,
    };
    Ok(HttpResponse::Created().json(category))
}

#[get("/{id}")]
pub async fn get_category(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = sqlx::query_as::<_, CategoryRow>(
        "SELECT id, name, description, created_at, updated_at \
         FROM categories WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(pool.get_ref())
    .await?;
    let category = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    Ok(HttpResponse::Ok().json(category))
}

#[put("/{id}")]
pub async fn update_category(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation("category name cannot be empty".to_string()));
    }
    let now = utc_iso8601();
    let res = sqlx::query(
        "UPDATE categories SET name = ?, description = ?, updated_at = ? WHERE id = ?",
    )
    .bind(&p.name)
    .bind(&p.description)
    .bind(&now)
    .bind(id)
    .execute(pool.get_ref())
    .await
    .map_err(|e| {
        if let sqlx::Error::Database(ref db_err) = e {
            if db_err.message().contains("UNIQUE") {
                return ApiError::Conflict(format!("category '{}' already exists", p.name));
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
    .fetch_one(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(row))
}

#[delete("/{id}")]
pub async fn delete_category(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let res = sqlx::query("DELETE FROM categories WHERE id = ?")
        .bind(id)
        .execute(pool.get_ref())
        .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("category {id} not found")));
    }
    Ok(HttpResponse::NoContent().finish())
}

fn utc_iso8601() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string()
}
