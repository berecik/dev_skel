//! HTTP handlers for `/api/orders`.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::orders::service::{
    AddLineDTO, AddressDTO, ApproveDTO, OrdersService, RejectDTO,
};
use crate::shared::ApiError;

#[derive(Debug, Deserialize)]
pub struct AddLinePayload {
    pub catalog_item_id: i32,
    #[serde(default = "default_quantity")]
    pub quantity: i32,
}

fn default_quantity() -> i32 {
    1
}

#[derive(Debug, Deserialize)]
pub struct AddressPayload {
    pub street: String,
    pub city: String,
    pub zip_code: String,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ApprovePayload {
    #[serde(default)]
    pub wait_minutes: Option<i32>,
    #[serde(default)]
    pub feedback: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct RejectPayload {
    #[serde(default)]
    pub feedback: Option<String>,
}

pub async fn create_order(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let inserted = svc.create_order(user.id as i32).await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn list_orders(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = svc.list_orders(user.id as i32).await?;
    Ok(Json(rows))
}

pub async fn get_order(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let detail = svc.get_detail(id, user.id as i32).await?;
    Ok(Json(detail))
}

pub async fn add_order_line(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<AddLinePayload>,
) -> Result<impl IntoResponse, ApiError> {
    let inserted = svc
        .add_line(
            order_id,
            user.id as i32,
            AddLineDTO {
                catalog_item_id: payload.catalog_item_id,
                quantity: payload.quantity,
            },
        )
        .await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

pub async fn remove_order_line(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path((order_id, line_id)): Path<(i32, i32)>,
) -> Result<impl IntoResponse, ApiError> {
    svc.delete_line(order_id, user.id as i32, line_id).await?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn set_order_address(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<AddressPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let saved = svc
        .upsert_address(
            order_id,
            user.id as i32,
            AddressDTO {
                street: payload.street,
                city: payload.city,
                zip_code: payload.zip_code,
                phone: payload.phone,
                notes: payload.notes,
            },
        )
        .await?;
    Ok(Json(saved))
}

pub async fn submit_order(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let updated = svc.submit(order_id, user.id as i32).await?;
    Ok(Json(updated))
}

pub async fn approve_order(
    State(svc): State<Arc<OrdersService>>,
    _user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<ApprovePayload>,
) -> Result<impl IntoResponse, ApiError> {
    let updated = svc
        .approve(
            order_id,
            ApproveDTO {
                wait_minutes: payload.wait_minutes,
                feedback: payload.feedback,
            },
        )
        .await?;
    Ok(Json(updated))
}

pub async fn reject_order(
    State(svc): State<Arc<OrdersService>>,
    _user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<RejectPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let updated = svc
        .reject(
            order_id,
            RejectDTO {
                feedback: payload.feedback,
            },
        )
        .await?;
    Ok(Json(updated))
}

pub async fn delete_order(
    State(svc): State<Arc<OrdersService>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    svc.delete(order_id, user.id as i32).await?;
    Ok(StatusCode::NO_CONTENT)
}
