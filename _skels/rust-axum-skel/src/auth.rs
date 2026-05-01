//! JWT mint / verify + Axum extractor for `Bearer <token>`.
//!
//! The token format matches the convention every dev_skel backend
//! follows: HS256-signed, `iss=devskel` (configurable via
//! `JWT_ISSUER`), `sub=<user_id>`, `exp` derived from
//! `JWT_ACCESS_TTL`. A token issued by django-bolt or fastapi is
//! accepted here and vice versa as long as the wrapper-shared
//! `JWT_SECRET` matches.

use std::sync::Arc;

use argon2::{
    password_hash::{rand_core::OsRng, SaltString},
    Argon2, PasswordHash, PasswordHasher, PasswordVerifier,
};
use async_trait::async_trait;
use axum::{
    extract::FromRequestParts,
    http::{header, request::Parts},
};
use chrono::Utc;
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use sea_orm::{EntityTrait, QuerySelect};
use serde::{Deserialize, Serialize};

use crate::config::Config;
use crate::entities::user;
use crate::error::ApiError;
use crate::AppState;

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
    pub id: i32,
    pub username: String,
}

#[async_trait]
impl FromRequestParts<Arc<AppState>> for AuthUser {
    type Rejection = ApiError;

    async fn from_request_parts(
        parts: &mut Parts,
        state: &Arc<AppState>,
    ) -> Result<Self, Self::Rejection> {
        let header_value = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|h| h.to_str().ok())
            .ok_or_else(|| {
                ApiError::Unauthorized("missing Authorization header".to_string())
            })?;
        let token = header_value.strip_prefix("Bearer ").ok_or_else(|| {
            ApiError::Unauthorized("Authorization header must start with 'Bearer '".to_string())
        })?;
        let claims = verify_token(token, &state.config)
            .map_err(|_| ApiError::Unauthorized("invalid or expired token".to_string()))?;
        if claims.token_type.as_deref() == Some("refresh") {
            return Err(ApiError::Unauthorized(
                "refresh token cannot authenticate this request".to_string(),
            ));
        }
        let user_id: i32 = claims
            .sub
            .parse()
            .map_err(|_| ApiError::Unauthorized("malformed sub claim".to_string()))?;

        let row = user::Entity::find_by_id(user_id)
            .select_only()
            .column(user::Column::Id)
            .column(user::Column::Username)
            .into_tuple::<(i32, String)>()
            .one(&state.db)
            .await
            .map_err(ApiError::Database)?;
        let (id, username) =
            row.ok_or_else(|| ApiError::Unauthorized("user no longer exists".to_string()))?;
        Ok(AuthUser { id, username })
    }
}
