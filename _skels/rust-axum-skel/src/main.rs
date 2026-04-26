//! Rust/Axum Skeleton Project
//!
//! Wires the wrapper-shared backend stack so the React frontend's
//! `/api/auth/*`, `/api/categories`, `/api/items`, and `/api/state`
//! calls work out-of-the-box. The schema mirrors the django-bolt skel
//! so a single `_shared/db.sqlite3` is interchangeable between
//! backends.

mod auth;
mod config;
mod db;
mod error;
mod handlers;
mod seed;

use axum::{
    extract::State,
    routing::get,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use sqlx::sqlite::SqlitePool;
use std::{net::SocketAddr, sync::Arc};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};

/// Shared application state. Handlers pull this out of the router
/// state via `State(Arc<AppState>)` so they never have to re-read
/// `std::env` or re-open the database pool.
#[derive(Clone)]
pub struct AppState {
    pub project_name: String,
    pub version: String,
    pub config: Config,
    pub pool: SqlitePool,
}

/// Project info response — served at `/`.
#[derive(Serialize, Deserialize)]
struct ProjectInfo {
    project: String,
    version: String,
    framework: String,
    status: String,
}

/// Health check response — served at `/health`.
#[derive(Serialize, Deserialize)]
struct HealthResponse {
    status: String,
}

async fn index(State(state): State<Arc<AppState>>) -> Json<ProjectInfo> {
    Json(ProjectInfo {
        project: state.project_name.clone(),
        version: state.version.clone(),
        framework: "Axum".to_string(),
        status: format!("running (issuer={})", state.config.jwt_issuer),
    })
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "healthy".to_string(),
    })
}

#[tokio::main]
async fn main() {
    // Load wrapper-shared `.env` first then the local one (idempotent
    // when nothing is present — keeps the skeleton runnable on a bare
    // clone).
    load_dotenv();

    let config = Config::from_env();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rust_axum_skel=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_host: std::net::IpAddr = config
        .service_host
        .parse()
        .unwrap_or_else(|_| std::net::IpAddr::from([0, 0, 0, 0]));
    let addr = SocketAddr::from((bind_host, config.service_port));
    tracing::info!(
        target: "rust_axum_skel",
        database_url = %config.database_url,
        jwt_issuer = %config.jwt_issuer,
        bind = %addr,
        "starting Axum server with wrapper-shared config",
    );

    // Connect + bootstrap schema before binding the listener so a bad
    // DB URL fails fast instead of returning 500s on every request.
    let pool = match db::connect_and_init(&config.database_url).await {
        Ok(p) => p,
        Err(e) => {
            tracing::error!(error = ?e, "failed to connect / init database");
            std::process::exit(1);
        }
    };

    // Seed default user accounts from env vars (idempotent).
    seed::seed_default_accounts(&pool).await;

    let state = Arc::new(AppState {
        project_name: "rust-axum-skel".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        config,
        pool,
    });

    let app = Router::new()
        .route("/", get(index))
        .route("/health", get(health))
        .merge(handlers::wrapper_router())
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind TCP listener");
    axum::serve(listener, app)
        .await
        .expect("axum server error");
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use axum_test::TestServer;

    async fn project_info_app() -> Router {
        let config = Config::from_env();
        // In-memory SQLite pool so the project-info tests do not
        // depend on a wrapper `.env`.
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .expect("in-memory sqlite");
        let state = Arc::new(AppState {
            project_name: "rust-axum-skel".to_string(),
            version: "1.0.0".to_string(),
            config,
            pool,
        });
        Router::new()
            .route("/", get(index))
            .route("/health", get(health))
            .with_state(state)
    }

    #[tokio::test]
    async fn test_index_returns_project_info() {
        let app = project_info_app().await;
        let server = TestServer::new(app).unwrap();

        let response = server.get("/").await;
        response.assert_status(StatusCode::OK);

        let body: ProjectInfo = response.json();
        assert_eq!(body.project, "rust-axum-skel");
        assert_eq!(body.framework, "Axum");
    }

    #[tokio::test]
    async fn test_health_endpoint() {
        let app = project_info_app().await;
        let server = TestServer::new(app).unwrap();

        let response = server.get("/health").await;
        response.assert_status(StatusCode::OK);

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
    }
}
