//! HTTP handlers for `/api/catalog`. GET endpoints are public; POST
//! requires a Bearer JWT (matches the wrapper-shared contract).

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::catalog::service::{CatalogService, NewCatalogItemDTO};
use crate::shared::ApiError;

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

pub async fn list_catalog(
    State(svc): State<Arc<CatalogService>>,
) -> Result<impl IntoResponse, ApiError> {
    let rows = svc.list().await?;
    Ok(Json(rows))
}

pub async fn create_catalog_item(
    State(svc): State<Arc<CatalogService>>,
    _user: AuthUser,
    Json(payload): Json<CatalogItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let inserted = svc
        .create(NewCatalogItemDTO {
            name: payload.name,
            description: payload.description,
            price: payload.price,
            category: payload.category,
            available: payload.available,
        })
        .await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn get_catalog_item(
    State(svc): State<Arc<CatalogService>>,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = svc.get(id).await?;
    Ok(Json(row))
}
