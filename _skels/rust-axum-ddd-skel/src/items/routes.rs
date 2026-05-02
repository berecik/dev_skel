//! HTTP handlers for `/api/items`. Thin: parse → call `ItemsService`
//! → translate `DomainError` via `ApiError`'s `IntoResponse` impl.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::items::service::{ItemsService, NewItemDTO};
use crate::shared::ApiError;

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
    State(svc): State<Arc<ItemsService>>,
    _user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = svc.list().await?;
    Ok(Json(rows))
}

pub async fn create_item(
    State(svc): State<Arc<ItemsService>>,
    _user: AuthUser,
    Json(payload): Json<CreateItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let inserted = svc
        .create(NewItemDTO {
            name: payload.name,
            description: payload.description,
            is_completed: payload.is_completed,
            category_id: payload.category_id,
        })
        .await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn get_item(
    State(svc): State<Arc<ItemsService>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let item = svc.get(id).await?;
    Ok(Json(item))
}

/// `POST /api/items/:id/complete` — flips `is_completed=true` and
/// returns the refreshed row. Idempotent.
pub async fn complete_item(
    State(svc): State<Arc<ItemsService>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let updated = svc.complete(id).await?;
    Ok(Json(updated))
}
