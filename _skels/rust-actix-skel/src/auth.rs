//! JWT mint / verify + Actix extractor for `Bearer <token>`.
//!
//! The token format matches the convention every dev_skel backend
//! follows: HS256-signed, `iss=devskel` (configurable via
//! `JWT_ISSUER`), `sub=<user_id>`, `exp` derived from
//! `JWT_ACCESS_TTL`. A token issued by django-bolt or fastapi is
//! accepted here and vice versa as long as the wrapper-shared
//! `JWT_SECRET` matches.

use std::pin::Pin;

use actix_web::{
    dev::Payload,
    web::Data,
    FromRequest, HttpRequest,
};
use argon2::{
    password_hash::{rand_core::OsRng, SaltString},
    Argon2, PasswordHash, PasswordHasher, PasswordVerifier,
};
use chrono::Utc;
use futures_util::future::Future;
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use sea_orm::{ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QuerySelect};
use serde::{Deserialize, Serialize};

use crate::config::Config;
use crate::entities::user;
use crate::error::ApiError;

/// JWT payload. We keep it small on purpose so a token issued by any
/// dev_skel backend roundtrips through any other.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    /// Subject — stringified user id.
    pub sub: String,
    /// Issuer — defaults to `devskel`, overridable via `JWT_ISSUER`.
    pub iss: String,
    /// Expiry as a Unix timestamp.
    pub exp: i64,
    /// Issued-at as a Unix timestamp.
    pub iat: i64,
    /// Optional `token_type` — `"refresh"` for refresh tokens, absent
    /// (or `"access"`) for access tokens.
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub token_type: Option<String>,
}

fn algorithm_from_str(name: &str) -> Algorithm {
    match name {
        "HS256" => Algorithm::HS256,
        "HS384" => Algorithm::HS384,
        "HS512" => Algorithm::HS512,
        // Anything we don't explicitly know about falls back to HS256
        // because the wrapper-shared `.env` defaults to HS256 and the
        // python skels hard-pin it.
        _ => Algorithm::HS256,
    }
}

/// Mint an access token for `user_id`. TTL is read from `Config`.
pub fn mint_access_token(user_id: i64, cfg: &Config) -> Result<String, ApiError> {
    mint_token(user_id, cfg, cfg.jwt_access_ttl as i64, None)
}

/// Mint a refresh token for `user_id`. TTL is read from `Config`.
pub fn mint_refresh_token(user_id: i64, cfg: &Config) -> Result<String, ApiError> {
    mint_token(user_id, cfg, cfg.jwt_refresh_ttl as i64, Some("refresh".to_string()))
}

fn mint_token(
    user_id: i64,
    cfg: &Config,
    ttl_seconds: i64,
    token_type: Option<String>,
) -> Result<String, ApiError> {
    let now = Utc::now().timestamp();
    let claims = Claims {
        sub: user_id.to_string(),
        iss: cfg.jwt_issuer.clone(),
        exp: now + ttl_seconds,
        iat: now,
        token_type,
    };
    let header = Header::new(algorithm_from_str(&cfg.jwt_algorithm));
    let key = EncodingKey::from_secret(cfg.jwt_secret.as_bytes());
    Ok(encode(&header, &claims, &key)?)
}

/// Decode + verify a token. Returns the parsed `Claims` on success.
pub fn verify_token(token: &str, cfg: &Config) -> Result<Claims, ApiError> {
    let mut validation = Validation::new(algorithm_from_str(&cfg.jwt_algorithm));
    validation.set_issuer(&[cfg.jwt_issuer.clone()]);
    let key = DecodingKey::from_secret(cfg.jwt_secret.as_bytes());
    let data = decode::<Claims>(token, &key, &validation)?;
    Ok(data.claims)
}

/// Hash a password using argon2 with a fresh random salt.
pub fn hash_password(password: &str) -> Result<String, ApiError> {
    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();
    let hash = argon2
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| ApiError::Password(e.to_string()))?
        .to_string();
    Ok(hash)
}

/// Verify a password against a stored argon2 hash.
pub fn verify_password(password: &str, stored_hash: &str) -> Result<bool, ApiError> {
    let parsed = PasswordHash::new(stored_hash).map_err(|e| ApiError::Password(e.to_string()))?;
    Ok(Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .is_ok())
}

/// Authenticated user context, populated by the `AuthUser` extractor
/// from the `Authorization: Bearer <token>` header. Handlers that need
/// to know who is calling them request this as an argument; the
/// extractor returns `Err(ApiError::Unauthorized)` when the header is
/// missing or the token is invalid, which becomes a 401 response.
#[derive(Debug, Clone)]
pub struct AuthUser {
    pub id: i64,
    pub username: String,
}

impl FromRequest for AuthUser {
    type Error = ApiError;
    type Future = Pin<Box<dyn Future<Output = Result<Self, Self::Error>>>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        let header_value = req
            .headers()
            .get(actix_web::http::header::AUTHORIZATION)
            .and_then(|h| h.to_str().ok())
            .map(|s| s.to_string());
        let cfg = req.app_data::<Data<Config>>().cloned();
        let db = req.app_data::<Data<DatabaseConnection>>().cloned();

        Box::pin(async move {
            let cfg = cfg.ok_or_else(|| {
                ApiError::Internal("Config not registered in app_data".to_string())
            })?;
            let db = db.ok_or_else(|| {
                ApiError::Internal(
                    "DatabaseConnection not registered in app_data".to_string(),
                )
            })?;

            let header = header_value.ok_or_else(|| {
                ApiError::Unauthorized("missing Authorization header".to_string())
            })?;
            let token = header.strip_prefix("Bearer ").ok_or_else(|| {
                ApiError::Unauthorized("Authorization header must start with 'Bearer '".to_string())
            })?;
            let claims = verify_token(token, &cfg)
                .map_err(|_| ApiError::Unauthorized("invalid or expired token".to_string()))?;
            // Reject refresh tokens here — only access tokens may
            // authenticate a regular request. (The /api/auth/refresh
            // endpoint, when added, can verify the refresh token via
            // `verify_token` directly and check `token_type`.)
            if claims.token_type.as_deref() == Some("refresh") {
                return Err(ApiError::Unauthorized(
                    "refresh token cannot authenticate this request".to_string(),
                ));
            }
            let user_id: i32 = claims
                .sub
                .parse()
                .map_err(|_| ApiError::Unauthorized("malformed sub claim".to_string()))?;

            // Pull only id + username via projection (matches the
            // legacy `SELECT id, username FROM users WHERE id = ?`).
            let row = user::Entity::find_by_id(user_id)
                .select_only()
                .column(user::Column::Id)
                .column(user::Column::Username)
                .into_tuple::<(i32, String)>()
                .one(db.get_ref())
                .await
                .map_err(ApiError::Database)?;
            let (id, username) = row.ok_or_else(|| {
                ApiError::Unauthorized("user no longer exists".to_string())
            })?;
            Ok(AuthUser {
                id: id as i64,
                username,
            })
        })
    }
}
