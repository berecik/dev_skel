//! HTTP handlers for `/api/orders`.

use actix_web::{delete, get, post, put, web, HttpResponse};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::orders::service::{
    AddLineDTO, AddressDTO, ApproveDTO, OrdersService, RejectDTO,
};
use crate::shared::DomainError;

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

#[post("")]
pub async fn create_order(
    svc: web::Data<OrdersService>,
    user: AuthUser,
) -> Result<HttpResponse, DomainError> {
    let inserted = svc.create_order(user.id as i32).await?;
    Ok(HttpResponse::Created().json(inserted))
}

#[get("")]
pub async fn list_orders(
    svc: web::Data<OrdersService>,
    user: AuthUser,
) -> Result<HttpResponse, DomainError> {
    let rows = svc.list_orders(user.id as i32).await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[get("/{id}")]
pub async fn get_order(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let detail = svc.get_detail(id, user.id as i32).await?;
    Ok(HttpResponse::Ok().json(detail))
}

#[post("/{id}/lines")]
pub async fn add_order_line(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<AddLinePayload>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    let p = payload.into_inner();
    let inserted = svc
        .add_line(
            order_id,
            user.id as i32,
            AddLineDTO {
                catalog_item_id: p.catalog_item_id,
                quantity: p.quantity,
            },
        )
        .await?;
    Ok(HttpResponse::Created().json(inserted))
}

#[delete("/{id}/lines/{line_id}")]
pub async fn remove_order_line(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<(i32, i32)>,
) -> Result<HttpResponse, DomainError> {
    let (order_id, line_id) = path.into_inner();
    svc.delete_line(order_id, user.id as i32, line_id).await?;
    Ok(HttpResponse::NoContent().finish())
}

#[put("/{id}/address")]
pub async fn set_order_address(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<AddressPayload>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    let p = payload.into_inner();
    let saved = svc
        .upsert_address(
            order_id,
            user.id as i32,
            AddressDTO {
                street: p.street,
                city: p.city,
                zip_code: p.zip_code,
                phone: p.phone,
                notes: p.notes,
            },
        )
        .await?;
    Ok(HttpResponse::Ok().json(saved))
}

#[post("/{id}/submit")]
pub async fn submit_order(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    let updated = svc.submit(order_id, user.id as i32).await?;
    Ok(HttpResponse::Ok().json(updated))
}

#[post("/{id}/approve")]
pub async fn approve_order(
    svc: web::Data<OrdersService>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<ApprovePayload>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    let p = payload.into_inner();
    let updated = svc
        .approve(
            order_id,
            ApproveDTO {
                wait_minutes: p.wait_minutes,
                feedback: p.feedback,
            },
        )
        .await?;
    Ok(HttpResponse::Ok().json(updated))
}

#[post("/{id}/reject")]
pub async fn reject_order(
    svc: web::Data<OrdersService>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<RejectPayload>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    let p = payload.into_inner();
    let updated = svc
        .reject(order_id, RejectDTO { feedback: p.feedback })
        .await?;
    Ok(HttpResponse::Ok().json(updated))
}

#[delete("/{id}")]
pub async fn delete_order(
    svc: web::Data<OrdersService>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let order_id = path.into_inner();
    svc.delete(order_id, user.id as i32).await?;
    Ok(HttpResponse::NoContent().finish())
}
