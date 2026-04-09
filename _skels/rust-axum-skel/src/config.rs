//! Wrapper-shared configuration module.
//!
//! Loads `<wrapper>/.env` first (so the abstract `DATABASE_URL`,
//! `JWT_SECRET`, and friends are inherited from the project root) and
//! then the local service `.env` for service-specific overrides.
//! Exposes typed accessors so handlers can pull a single `Config` instance
//! out of the Axum router state instead of repeatedly probing `std::env`.

use std::{env, path::PathBuf};

/// Strongly-typed wrapper-shared config.
#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub jwt_secret: String,
    pub jwt_algorithm: String,
    pub jwt_issuer: String,
    pub jwt_access_ttl: u64,
    pub jwt_refresh_ttl: u64,
    pub service_host: String,
    pub service_port: u16,
}

impl Config {
    /// Build a [`Config`] from the process environment.
    ///
    /// Sane defaults keep the skeleton runnable on a bare clone — when
    /// the wrapper-shared `.env` is not available we fall back to a
    /// per-service sqlite file and a placeholder JWT secret.
    pub fn from_env() -> Self {
        Self {
            database_url: env::var("DATABASE_URL")
                .unwrap_or_else(|_| "sqlite://./service.db".to_string()),
            jwt_secret: env::var("JWT_SECRET")
                .unwrap_or_else(|_| "change-me-32-bytes-of-random-data".to_string()),
            jwt_algorithm: env::var("JWT_ALGORITHM").unwrap_or_else(|_| "HS256".to_string()),
            jwt_issuer: env::var("JWT_ISSUER").unwrap_or_else(|_| "devskel".to_string()),
            jwt_access_ttl: env::var("JWT_ACCESS_TTL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3600),
            jwt_refresh_ttl: env::var("JWT_REFRESH_TTL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(604_800),
            service_host: env::var("SERVICE_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            service_port: env::var("SERVICE_PORT")
                .or_else(|_| env::var("PORT"))
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3000),
        }
    }
}

/// Load `<wrapper>/.env` then the local `./.env` (if present) so child
/// processes inherit the shared environment.
///
/// The wrapper directory is the **parent** of the service directory by
/// dev_skel convention; we walk up one level looking for a `.env` file.
pub fn load_dotenv() {
    if let Some(wrapper_env) = wrapper_env_path() {
        let _ = dotenvy::from_path(wrapper_env);
    }
    if std::path::Path::new(".env").is_file() {
        let _ = dotenvy::from_path_override(".env");
    }
}

fn wrapper_env_path() -> Option<PathBuf> {
    let cwd = env::current_dir().ok()?;
    let parent = cwd.parent()?;
    let candidate = parent.join(".env");
    if candidate.is_file() {
        Some(candidate)
    } else {
        None
    }
}
