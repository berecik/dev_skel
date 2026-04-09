//! Rust/Axum Skeleton Project

mod config;

use axum::{
    extract::State,
    routing::get,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::{net::SocketAddr, sync::Arc};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};

/// Application state — holds the wrapper-shared `Config` so handlers can
/// pull it out of the router state instead of re-reading the environment.
#[derive(Clone)]
struct AppState {
    project_name: String,
    version: String,
    #[allow(dead_code)]
    config: Config,
}

/// Project info response
#[derive(Serialize, Deserialize)]
struct ProjectInfo {
    project: String,
    version: String,
    framework: String,
    status: String,
}

/// Health check response
#[derive(Serialize, Deserialize)]
struct HealthResponse {
    status: String,
}

/// Root endpoint returning project info
async fn index(State(state): State<Arc<AppState>>) -> Json<ProjectInfo> {
    Json(ProjectInfo {
        project: state.project_name.clone(),
        version: state.version.clone(),
        framework: "Axum".to_string(),
        status: "running".to_string(),
    })
}

/// Health check endpoint
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

    // Initialize tracing
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

    let state = Arc::new(AppState {
        project_name: "rust-axum-skel".to_string(),
        version: "1.0.0".to_string(),
        config,
    });

    // Build router
    let app = Router::new()
        .route("/", get(index))
        .route("/health", get(health))
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;
    use axum_test::TestServer;

    fn create_test_app() -> Router {
        let state = Arc::new(AppState {
            project_name: "rust-axum-skel".to_string(),
            version: "1.0.0".to_string(),
            config: Config::from_env(),
        });

        Router::new()
            .route("/", get(index))
            .route("/health", get(health))
            .with_state(state)
    }

    #[tokio::test]
    async fn test_index_returns_project_info() {
        let app = create_test_app();
        let server = TestServer::new(app).unwrap();

        let response = server.get("/").await;
        response.assert_status(StatusCode::OK);

        let body: ProjectInfo = response.json();
        assert_eq!(body.project, "rust-axum-skel");
        assert_eq!(body.framework, "Axum");
    }

    #[tokio::test]
    async fn test_health_endpoint() {
        let app = create_test_app();
        let server = TestServer::new(app).unwrap();

        let response = server.get("/health").await;
        response.assert_status(StatusCode::OK);

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
    }
}
