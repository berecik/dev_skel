//! HTTP handlers for `/api/items`. Thin: parse → call `ItemsService`
//! → translate `DomainError` via the shared `ResponseError` impl.

use actix_web::{get, post, web, HttpResponse};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::items::service::{ItemsService, NewItemDTO};
use crate::shared::DomainError;

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
    svc: web::Data<ItemsService>,
    _user: AuthUser,
) -> Result<HttpResponse, DomainError> {
    let rows = svc.list().await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_item(
    svc: web::Data<ItemsService>,
    _user: AuthUser,
    payload: web::Json<CreateItemPayload>,
) -> Result<HttpResponse, DomainError> {
    let p = payload.into_inner();
    let inserted = svc
        .create(NewItemDTO {
            name: p.name,
            description: p.description,
            is_completed: p.is_completed,
            category_id: p.category_id,
        })
        .await?;
    Ok(HttpResponse::Created().json(inserted))
}

#[get("/{id}")]
pub async fn get_item(
    svc: web::Data<ItemsService>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let item = svc.get(id).await?;
    Ok(HttpResponse::Ok().json(item))
}

/// `POST /api/items/{id}/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent.
#[post("/{id}/complete")]
pub async fn complete_item(
    svc: web::Data<ItemsService>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let updated = svc.complete(id).await?;
    Ok(HttpResponse::Ok().json(updated))
}
