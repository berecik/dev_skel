//! HTTP handlers for `/api/catalog`. GET endpoints are public; POST
//! requires a Bearer JWT (matches the wrapper-shared contract).

use actix_web::{get, post, web, HttpResponse};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::catalog::service::{CatalogService, NewCatalogItemDTO};
use crate::shared::DomainError;

#[derive(Debug, Deserialize)]
pub struct CatalogItemPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    pub price: f64,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default = "default_available")]
    pub available: bool,
}

fn default_available() -> bool {
    true
}

#[get("")]
pub async fn list_catalog(
    svc: web::Data<CatalogService>,
) -> Result<HttpResponse, DomainError> {
    let rows = svc.list().await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_catalog_item(
    svc: web::Data<CatalogService>,
    _user: AuthUser,
    payload: web::Json<CatalogItemPayload>,
) -> Result<HttpResponse, DomainError> {
    let p = payload.into_inner();
    let inserted = svc
        .create(NewCatalogItemDTO {
            name: p.name,
            description: p.description,
            price: p.price,
            category: p.category,
            available: p.available,
        })
        .await?;
    Ok(HttpResponse::Created().json(inserted))
}

#[get("/{id}")]
pub async fn get_catalog_item(
    svc: web::Data<CatalogService>,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let row = svc.get(id).await?;
    Ok(HttpResponse::Ok().json(row))
}
