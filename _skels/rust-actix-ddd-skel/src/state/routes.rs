//! HTTP handlers for `/api/state`.

use actix_web::{delete, get, http::header, put, web, HttpResponse};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::shared::DomainError;
use crate::state::service::StateService;

#[derive(Debug, Deserialize)]
pub struct UpsertPayload {
    pub value: String,
}

#[get("")]
pub async fn list_state(
    svc: web::Data<StateService>,
    user: AuthUser,
) -> Result<HttpResponse, DomainError> {
    let map = svc.map(user.id as i32).await?;
    Ok(HttpResponse::Ok().json(map))
}

#[put("/{key}")]
pub async fn upsert_state(
    svc: web::Data<StateService>,
    user: AuthUser,
    path: web::Path<String>,
    payload: web::Json<UpsertPayload>,
) -> Result<HttpResponse, DomainError> {
    let key = path.into_inner();
    let body = payload.into_inner();
    svc.upsert(user.id as i32, &key, body.value).await?;
    Ok(HttpResponse::Ok().json(serde_json::json!({ "key": key })))
}

#[delete("/{key}")]
pub async fn delete_state(
    svc: web::Data<StateService>,
    user: AuthUser,
    path: web::Path<String>,
) -> Result<HttpResponse, DomainError> {
    let key = path.into_inner();
    svc.delete(user.id as i32, &key).await?;
    Ok(HttpResponse::Ok()
        .insert_header((header::CONTENT_TYPE, "application/json"))
        .body("{}"))
}
