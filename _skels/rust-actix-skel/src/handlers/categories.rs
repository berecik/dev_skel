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
use sea_orm::sea_query::OnConflict;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, DbErr, EntityTrait, ModelTrait,
    QueryFilter, QueryOrder, RuntimeErr, Set,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::category;
use crate::error::ApiError;

#[derive(Debug, Deserialize)]
pub struct CreateCategoryPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

#[get("")]
pub async fn list_categories(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = category::Entity::find()
        .order_by_asc(category::Column::Name)
        .all(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_category(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "category name cannot be empty".to_string(),
        ));
    }
    let now = Utc::now();
    let new_cat = category::ActiveModel {
        name: Set(p.name.clone()),
        description: Set(p.description),
        created_at: Set(now),
        updated_at: Set(now),
        ..Default::default()
    };
    let inserted = new_cat.insert(db.get_ref()).await.map_err(|e| {
        if is_unique_violation(&e) {
            ApiError::Conflict(format!("category '{}' already exists", p.name))
        } else {
            ApiError::Database(e)
        }
    })?;
    Ok(HttpResponse::Created().json(inserted))
}

#[get("/{id}")]
pub async fn get_category(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = category::Entity::find_by_id(id).one(db.get_ref()).await?;
    let cat = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    Ok(HttpResponse::Ok().json(cat))
}

#[put("/{id}")]
pub async fn update_category(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "category name cannot be empty".to_string(),
        ));
    }
    let row = category::Entity::find_by_id(id).one(db.get_ref()).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;

    let mut active: category::ActiveModel = existing.into();
    active.name = Set(p.name.clone());
    active.description = Set(p.description);
    active.updated_at = Set(Utc::now());
    let updated = active.update(db.get_ref()).await.map_err(|e| {
        if is_unique_violation(&e) {
            ApiError::Conflict(format!("category '{}' already exists", p.name))
        } else {
            ApiError::Database(e)
        }
    })?;
    Ok(HttpResponse::Ok().json(updated))
}

#[delete("/{id}")]
pub async fn delete_category(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = category::Entity::find_by_id(id).one(db.get_ref()).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("category {id} not found")))?;
    existing.delete(db.get_ref()).await?;
    Ok(HttpResponse::NoContent().finish())
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
