//! HTTP handlers for `/api/categories`.

use actix_web::{delete, get, post, put, web, HttpResponse};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::categories::service::{CategoriesService, NewCategoryDTO};
use crate::shared::DomainError;

#[derive(Debug, Deserialize)]
pub struct CreateCategoryPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

#[get("")]
pub async fn list_categories(
    svc: web::Data<CategoriesService>,
    _user: AuthUser,
) -> Result<HttpResponse, DomainError> {
    let rows = svc.list().await?;
    Ok(HttpResponse::Ok().json(rows))
}

#[post("")]
pub async fn create_category(
    svc: web::Data<CategoriesService>,
    _user: AuthUser,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, DomainError> {
    let p = payload.into_inner();
    let created = svc
        .create(NewCategoryDTO {
            name: p.name,
            description: p.description,
        })
        .await?;
    Ok(HttpResponse::Created().json(created))
}

#[get("/{id}")]
pub async fn get_category(
    svc: web::Data<CategoriesService>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let row = svc.get(id).await?;
    Ok(HttpResponse::Ok().json(row))
}

#[put("/{id}")]
pub async fn update_category(
    svc: web::Data<CategoriesService>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<CreateCategoryPayload>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    let p = payload.into_inner();
    let updated = svc
        .update(
            id,
            NewCategoryDTO {
                name: p.name,
                description: p.description,
            },
        )
        .await?;
    Ok(HttpResponse::Ok().json(updated))
}

#[delete("/{id}")]
pub async fn delete_category(
    svc: web::Data<CategoriesService>,
    _user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, DomainError> {
    let id = path.into_inner();
    svc.delete(id).await?;
    Ok(HttpResponse::NoContent().finish())
}
