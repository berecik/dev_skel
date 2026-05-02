//! HTTP handlers for `/api/categories`.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::categories::service::{CategoriesService, NewCategoryDTO};
use crate::shared::ApiError;

#[derive(Debug, Deserialize)]
pub struct CreateCategoryPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

pub async fn list_categories(
    State(svc): State<Arc<CategoriesService>>,
    _user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = svc.list().await?;
    Ok(Json(rows))
}

pub async fn create_category(
    State(svc): State<Arc<CategoriesService>>,
    _user: AuthUser,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let created = svc
        .create(NewCategoryDTO {
            name: payload.name,
            description: payload.description,
        })
        .await?;
    Ok((StatusCode::CREATED, Json(created)))
}

pub async fn get_category(
    State(svc): State<Arc<CategoriesService>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = svc.get(id).await?;
    Ok(Json(row))
}

pub async fn update_category(
    State(svc): State<Arc<CategoriesService>>,
    _user: AuthUser,
    Path(id): Path<i32>,
    Json(payload): Json<CreateCategoryPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let updated = svc
        .update(
            id,
            NewCategoryDTO {
                name: payload.name,
                description: payload.description,
            },
        )
        .await?;
    Ok(Json(updated))
}

pub async fn delete_category(
    State(svc): State<Arc<CategoriesService>>,
    _user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    svc.delete(id).await?;
    Ok(StatusCode::NO_CONTENT)
}
