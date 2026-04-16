//! `/api/auth/register` and `/api/auth/login` — JWT bearer auth.
//!
//! Response shapes match the contract every dev_skel backend honours
//! so the React frontend's `src/api/auth.ts` works against any of them
//! without a code change:
//!
//! * register → 201 `{ user: { id, username, email }, access, refresh }`
//! * login → 200 `{ access, refresh, user_id, username }`

use actix_web::{post, web, HttpResponse};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sqlx::sqlite::SqlitePool;

use crate::auth::{hash_password, mint_access_token, mint_refresh_token, verify_password};
use crate::config::Config;
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
    id: i64,
    username: String,
    email: String,
}

#[post("/register")]
pub async fn register_handler(
    pool: web::Data<SqlitePool>,
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
    let existing: Option<(i64,)> = sqlx::query_as("SELECT id FROM users WHERE username = ?")
        .bind(&p.username)
        .fetch_optional(pool.get_ref())
        .await?;
    if existing.is_some() {
        return Err(ApiError::Conflict(format!(
            "user '{}' already exists",
            p.username
        )));
    }

    let hash = hash_password(&p.password)?;
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?) RETURNING id",
    )
    .bind(&p.username)
    .bind(&p.email)
    .bind(&hash)
    .fetch_one(pool.get_ref())
    .await?;
    let new_id = row.0;

    let access = mint_access_token(new_id, &cfg)?;
    let refresh = mint_refresh_token(new_id, &cfg)?;

    Ok(HttpResponse::Created().json(json!({
        "user": UserOut { id: new_id, username: p.username.clone(), email: p.email.clone() },
        "access": access,
        "refresh": refresh,
    })))
}

#[post("/login")]
pub async fn login_handler(
    pool: web::Data<SqlitePool>,
    cfg: web::Data<Config>,
    payload: web::Json<LoginPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    let row: Option<(i64, String, String)> = sqlx::query_as(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
    )
    .bind(&p.username)
    .fetch_optional(pool.get_ref())
    .await?;

    let (id, username, password_hash) = row.ok_or_else(|| {
        ApiError::Unauthorized("invalid username or password".to_string())
    })?;

    if !verify_password(&p.password, &password_hash)? {
        return Err(ApiError::Unauthorized(
            "invalid username or password".to_string(),
        ));
    }

    let access = mint_access_token(id, &cfg)?;
    let refresh = mint_refresh_token(id, &cfg)?;

    Ok(HttpResponse::Ok().json(json!({
        "access": access,
        "refresh": refresh,
        "user_id": id,
        "username": username,
    })))
}
