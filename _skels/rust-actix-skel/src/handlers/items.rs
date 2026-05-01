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
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryOrder, Set,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::item;
use crate::error::ApiError;

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

#[get("")]
pub async fn list_items(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = item::Entity::find()
        .order_by_desc(item::Column::CreatedAt)
        .order_by_desc(item::Column::Id)
        .all(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_item(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    payload: web::Json<CreateItemPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "item name cannot be empty".to_string(),
        ));
    }
    let now = Utc::now();
    let new_item = item::ActiveModel {
        name: Set(p.name),
        description: Set(p.description),
        is_completed: Set(p.is_completed),
        category_id: Set(p.category_id),
        created_at: Set(now),
        updated_at: Set(now),
        ..Default::default()
    };
    let inserted = new_item.insert(db.get_ref()).await?;
    Ok(HttpResponse::Created().json(inserted))
}

#[get("/{id}")]
pub async fn get_item(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = item::Entity::find_by_id(id).one(db.get_ref()).await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;
    Ok(HttpResponse::Ok().json(item))
}

/// `POST /api/items/{id}/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent: completing an already-
/// completed item is a no-op that still returns 200.
#[post("/{id}/complete")]
pub async fn complete_item(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = item::Entity::find_by_id(id).one(db.get_ref()).await?;
    let existing = row.ok_or_else(|| ApiError::NotFound(format!("item {id} not found")))?;

    let mut active: item::ActiveModel = existing.into();
    active.is_completed = Set(true);
    active.updated_at = Set(Utc::now());
    let updated = active.update(db.get_ref()).await?;
    Ok(HttpResponse::Ok().json(updated))
}
