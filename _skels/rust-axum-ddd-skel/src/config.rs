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
        let raw_database_url = env::var("DATABASE_URL")
            .unwrap_or_else(|_| "sqlite://./service.db".to_string());
        let database_url = normalize_sqlite_url(&raw_database_url);
        Self {
            database_url,
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

/// Translate a Python-flavored `sqlite:///relative/path` URL into a form
/// sqlx accepts and that resolves against the wrapper directory.
///
/// Background: `<wrapper>/.env` ships
/// `DATABASE_URL=sqlite:///_shared/db.sqlite3`. In SQLAlchemy / Django
/// the triple-slash prefix means "relative to the cwd"; in sqlx the
/// triple slash means "absolute path", which would resolve to
/// `/_shared/db.sqlite3` and fail. We work around it by:
///
/// 1. Stripping the `sqlite:` / `sqlite://` / `sqlite:///` prefix down
///    to the bare path component.
/// 2. If the path does not start with `/`, treat it as relative to the
///    wrapper directory (the parent of the service dir, by dev_skel
///    convention) so different services can share one database file
///    regardless of which one is the cwd.
/// 3. Re-emit a `sqlite://<absolute-path>?mode=rwc` URL so sqlx will
///    auto-create the file on first connect.
///
/// Non-sqlite URLs (postgres://, mysql://, ...) are passed through
/// unchanged because the wrapper convention only translates sqlite.
pub fn normalize_sqlite_url(raw: &str) -> String {
    if !raw.starts_with("sqlite:") {
        return raw.to_string();
    }
    let path_part = raw
        .strip_prefix("sqlite:///")
        .or_else(|| raw.strip_prefix("sqlite://"))
        .or_else(|| raw.strip_prefix("sqlite:"))
        .unwrap_or(raw);

    if path_part == ":memory:" {
        return "sqlite::memory:".to_string();
    }

    let (path_only, _existing_query) = match path_part.find('?') {
        Some(idx) => (&path_part[..idx], &path_part[idx..]),
        None => (path_part, ""),
    };

    let candidate = std::path::Path::new(path_only);
    let resolved: PathBuf = if candidate.is_absolute() {
        candidate.to_path_buf()
    } else if let Some(wrapper) = wrapper_dir() {
        wrapper.join(candidate)
    } else {
        candidate.to_path_buf()
    };

    let resolved_str = resolved.to_string_lossy();
    format!("sqlite://{}?mode=rwc", resolved_str)
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

fn wrapper_dir() -> Option<PathBuf> {
    let cwd = env::current_dir().ok()?;
    let parent = cwd.parent()?;
    Some(parent.to_path_buf())
}

fn wrapper_env_path() -> Option<PathBuf> {
    let candidate = wrapper_dir()?.join(".env");
    if candidate.is_file() {
        Some(candidate)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_passes_through_postgres_url() {
        let s = normalize_sqlite_url("postgres://user:pw@host/db");
        assert_eq!(s, "postgres://user:pw@host/db");
    }

    #[test]
    fn normalize_handles_in_memory_marker() {
        let s = normalize_sqlite_url("sqlite::memory:");
        assert_eq!(s, "sqlite::memory:");
    }

    #[test]
    fn normalize_makes_relative_sqlite_absolute() {
        let s = normalize_sqlite_url("sqlite:///_shared/db.sqlite3");
        assert!(s.starts_with("sqlite://"), "got: {s}");
        assert!(s.ends_with("?mode=rwc"));
        let path_part = s
            .strip_prefix("sqlite://")
            .unwrap()
            .split('?')
            .next()
            .unwrap();
        assert!(path_part.starts_with('/'), "expected absolute path, got: {path_part}");
    }
}
