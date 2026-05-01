//! `/api/auth/register` and `/api/auth/login` — JWT bearer auth.
//!
//! Response shapes match the contract every dev_skel backend honours
//! so the React frontend's `src/api/auth.ts` works against any of them
//! without a code change:
//!
//! * register → 201 `{ user: { id, username, email }, access, refresh }`
//! * login → 200 `{ access, refresh, user_id, username }`

use actix_web::{post, web, HttpResponse};
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, Set,
};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::auth::{hash_password, mint_access_token, mint_refresh_token, verify_password};
use crate::config::Config;
use crate::entities::user;
use crate::error::ApiError;

#[derive(Debug, Deserialize)]
pub struct RegisterPayload {
    pub username: String,
    pub email: String,
    pub password: String,
    /// Optional confirmation field — the React skel sends it; we accept
    /// it without it being required so other clients (curl, the smoke
    /// runner) can omit it.
    #[serde(default)]
    pub password_confirm: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoginPayload {
    pub username: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
struct UserOut {
    id: i32,
    username: String,
    email: String,
}

#[post("/register")]
pub async fn register_handler(
    db: web::Data<DatabaseConnection>,
    cfg: web::Data<Config>,
    payload: web::Json<RegisterPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.username.trim().is_empty() {
        return Err(ApiError::Validation("username cannot be empty".to_string()));
    }
    if p.password.len() < 6 {
        return Err(ApiError::Validation(
            "password must be at least 6 characters".to_string(),
        ));
    }
    if let Some(confirm) = &p.password_confirm {
        if confirm != &p.password {
            return Err(ApiError::Validation(
                "password and password_confirm do not match".to_string(),
            ));
        }
    }

    // Reject duplicate usernames with 409 (matches the contract every
    // other dev_skel backend honours; the React frontend surfaces 4xx
    // errors to the user verbatim via fetch + AuthError).
    let existing = user::Entity::find()
        .filter(user::Column::Username.eq(&p.username))
        .one(db.get_ref())
        .await?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!(
            "user '{}' already exists",
            p.username
        )));
    }

    let hash = hash_password(&p.password)?;
    let new_user = user::ActiveModel {
        username: Set(p.username.clone()),
        email: Set(p.email.clone()),
        password_hash: Set(hash),
        created_at: Set(Utc::now()),
        ..Default::default()
    };
    let inserted = new_user.insert(db.get_ref()).await?;
    let new_id = inserted.id;

    let access = mint_access_token(new_id as i64, &cfg)?;
    let refresh = mint_refresh_token(new_id as i64, &cfg)?;

    Ok(HttpResponse::Created().json(json!({
        "user": UserOut { id: new_id, username: p.username.clone(), email: p.email.clone() },
        "access": access,
        "refresh": refresh,
    })))
}

#[post("/login")]
pub async fn login_handler(
    db: web::Data<DatabaseConnection>,
    cfg: web::Data<Config>,
    payload: web::Json<LoginPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    let column_filter = if p.username.contains('@') {
        user::Column::Email
    } else {
        user::Column::Username
    };
    let row = user::Entity::find()
        .filter(column_filter.eq(&p.username))
        .one(db.get_ref())
        .await?;

    let user_row = row.ok_or_else(|| {
        ApiError::Unauthorized("invalid username or password".to_string())
    })?;

    if !verify_password(&p.password, &user_row.password_hash)? {
        return Err(ApiError::Unauthorized(
            "invalid username or password".to_string(),
        ));
    }

    let access = mint_access_token(user_row.id as i64, &cfg)?;
    let refresh = mint_refresh_token(user_row.id as i64, &cfg)?;

    Ok(HttpResponse::Ok().json(json!({
        "access": access,
        "refresh": refresh,
        "user_id": user_row.id,
        "username": user_row.username,
    })))
}
