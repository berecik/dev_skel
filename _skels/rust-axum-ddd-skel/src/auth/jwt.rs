//! JWT mint / verify + the `AuthUser` axum extractor.
//!
//! The token format matches the convention every dev_skel backend
//! follows: HS256-signed, `iss=devskel` (configurable via
//! `JWT_ISSUER`), `sub=<user_id>`, `exp` derived from
//! `JWT_ACCESS_TTL`. A token issued by django-bolt or fastapi is
//! accepted here and vice versa as long as the wrapper-shared
//! `JWT_SECRET` matches.
//!
//! The extractor talks to `users::UserRepository` (not
//! `DatabaseConnection`) for principal lookup so the auth layer never
//! sees SeaORM directly. It pulls the `AppContext` (which carries
//! `Config` + boxed `UserRepository`) out of any router state via
//! `axum::extract::FromRef` so every per-resource subrouter can host
//! handlers that ask for `AuthUser`.

use async_trait::async_trait;
use axum::{
    extract::{FromRef, FromRequestParts},
    http::{header, request::Parts},
};
use chrono::Utc;
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};

use crate::config::Config;
use crate::shared::{ApiError, AppContext, DomainError};

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
pub fn mint_access_token(user_id: i64, cfg: &Config) -> Result<String, DomainError> {
    mint_token(user_id, cfg, cfg.jwt_access_ttl as i64, None)
}

/// Mint a refresh token for `user_id`. TTL is read from `Config`.
pub fn mint_refresh_token(user_id: i64, cfg: &Config) -> Result<String, DomainError> {
    mint_token(
        user_id,
        cfg,
        cfg.jwt_refresh_ttl as i64,
        Some("refresh".to_string()),
    )
}

fn mint_token(
    user_id: i64,
    cfg: &Config,
    ttl_seconds: i64,
    token_type: Option<String>,
) -> Result<String, DomainError> {
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
pub fn verify_token(token: &str, cfg: &Config) -> Result<Claims, DomainError> {
    let mut validation = Validation::new(algorithm_from_str(&cfg.jwt_algorithm));
    validation.set_issuer(std::slice::from_ref(&cfg.jwt_issuer));
    let key = DecodingKey::from_secret(cfg.jwt_secret.as_bytes());
    let data = decode::<Claims>(token, &key, &validation)?;
    Ok(data.claims)
}

/// Authenticated user context, populated by the `AuthUser` extractor
/// from the `Authorization: Bearer <token>` header. Handlers that
/// need to know who is calling them request this as an argument; the
/// extractor returns `Err(ApiError(DomainError::Unauthorized))` when
/// the header is missing or the token is invalid, which becomes a 401
/// response.
#[derive(Debug, Clone)]
pub struct AuthUser {
    pub id: i64,
    #[allow(dead_code)]
    pub username: String,
}

#[async_trait]
impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
    AppContext: FromRef<S>,
{
    type Rejection = ApiError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let ctx = AppContext::from_ref(state);

        let header_value = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|h| h.to_str().ok())
            .ok_or_else(|| {
                ApiError::from(DomainError::Unauthorized(
                    "missing Authorization header".to_string(),
                ))
            })?;
        let token = header_value.strip_prefix("Bearer ").ok_or_else(|| {
            ApiError::from(DomainError::Unauthorized(
                "Authorization header must start with 'Bearer '".to_string(),
            ))
        })?;
        let claims = verify_token(token, &ctx.config).map_err(|_| {
            ApiError::from(DomainError::Unauthorized(
                "invalid or expired token".to_string(),
            ))
        })?;
        if claims.token_type.as_deref() == Some("refresh") {
            return Err(ApiError::from(DomainError::Unauthorized(
                "refresh token cannot authenticate this request".to_string(),
            )));
        }
        let user_id: i32 = claims.sub.parse().map_err(|_| {
            ApiError::from(DomainError::Unauthorized(
                "malformed sub claim".to_string(),
            ))
        })?;

        let (id, username) = ctx
            .user_repo
            .principal(user_id)
            .await
            .map_err(|err| match err {
                DomainError::NotFound(_) => ApiError::from(DomainError::Unauthorized(
                    "user no longer exists".to_string(),
                )),
                other => ApiError::from(other),
            })?;

        Ok(AuthUser {
            id: id as i64,
            username,
        })
    }
}
