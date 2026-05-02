//! `/api/auth/{register, login}` HTTP handlers. Thin: parse → call
//! `AuthService` → translate domain errors into HTTP via the
//! `ResponseError` impl on `DomainError`.

use actix_web::{post, web, HttpResponse};
use serde::Deserialize;
use serde_json::json;

use crate::auth::service::{AuthService, LoginDTO, RegisterDTO};
use crate::shared::DomainError;

#[derive(Debug, Deserialize)]
pub struct RegisterPayload {
    pub username: String,
    pub email: String,
    pub password: String,
    /// Optional confirmation field — the React skel sends it; we
    /// accept it without it being required so other clients (curl,
    /// the smoke runner) can omit it.
    #[serde(default)]
    pub password_confirm: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoginPayload {
    pub username: String,
    pub password: String,
}

#[post("/register")]
pub async fn register_handler(
    svc: web::Data<AuthService>,
    payload: web::Json<RegisterPayload>,
) -> Result<HttpResponse, DomainError> {
    let p = payload.into_inner();
    let res = svc
        .register(RegisterDTO {
            username: p.username,
            email: p.email,
            password: p.password,
            password_confirm: p.password_confirm,
        })
        .await?;

    Ok(HttpResponse::Created().json(json!({
        "user": {
            "id": res.user.id,
            "username": res.user.username,
            "email": res.user.email,
        },
        "access": res.access,
        "refresh": res.refresh,
    })))
}

#[post("/login")]
pub async fn login_handler(
    svc: web::Data<AuthService>,
    payload: web::Json<LoginPayload>,
) -> Result<HttpResponse, DomainError> {
    let p = payload.into_inner();
    let res = svc
        .login(LoginDTO {
            username_or_email: p.username,
            password: p.password,
        })
        .await?;

    Ok(HttpResponse::Ok().json(json!({
        "access": res.access,
        "refresh": res.refresh,
        "user_id": res.user.id,
        "username": res.user.username,
    })))
}
