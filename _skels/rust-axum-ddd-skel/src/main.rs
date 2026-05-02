//! Rust/Axum Skeleton Project
//!
//! Wires the wrapper-shared backend stack so the React frontend's
//! `/api/auth/*`, `/api/categories`, `/api/items`, `/api/state`,
//! `/api/catalog`, and `/api/orders` calls work out-of-the-box.
//!
//! Resources are organised as light-DDD layers under `src/`: each
//! resource (items, categories, orders, catalog, state, users, auth)
//! owns a `Repository` trait, an adapter implementing it via SeaORM,
//! a `Service`, a `routes.rs` that wires HTTP to the service, and a
//! `depts.rs` that composes them into an axum `Router`. `main.rs`'s
//! job is just to merge them.

mod auth;
mod catalog;
mod categories;
mod config;
mod db;
mod entities;
mod items;
mod orders;
mod seed;
mod shared;
mod state;
mod users;

use std::{net::SocketAddr, sync::Arc};

use axum::{routing::get, Json, Router};
use serde::{Deserialize, Serialize};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};
use crate::shared::AppContext;
use crate::users::UserRepository;

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

async fn index() -> Json<ProjectInfo> {
    Json(ProjectInfo {
        project: "rust-axum-ddd-skel".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        framework: "Axum".to_string(),
        status: "running".to_string(),
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
                .unwrap_or_else(|_| "rust_axum_ddd_skel=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_host: std::net::IpAddr = config
        .service_host
        .parse()
        .unwrap_or_else(|_| std::net::IpAddr::from([0, 0, 0, 0]));
    let addr = SocketAddr::from((bind_host, config.service_port));
    tracing::info!(
        target: "rust_axum_ddd_skel",
        database_url = %config.database_url,
        jwt_issuer = %config.jwt_issuer,
        bind = %addr,
        "starting Axum server with wrapper-shared config",
    );

    // Connect + bootstrap schema before binding the listener so a bad
    // DB URL fails fast instead of returning 500s on every request.
    let conn = match db::connect_and_init(&config.database_url).await {
        Ok(c) => c,
        Err(e) => {
            tracing::error!(error = ?e, "failed to connect / init database");
            std::process::exit(1);
        }
    };
    let conn = Arc::new(conn);

    // Build the user repository once and share it: seed, the auth
    // service, and the JWT extractor all reach for the same handle.
    let user_repo: Arc<dyn UserRepository> =
        Arc::new(users::SeaUserRepository::new(conn.clone()));

    if let Err(e) = seed::seed_default_accounts(user_repo.clone()).await {
        tracing::error!(error = ?e, "failed to seed default accounts");
    }

    // Composition handle the auth extractor reaches for via
    // `FromRef<RouterState> for AppContext` from each resource's
    // depts.rs.
    let ctx = AppContext::new(config.clone(), user_repo);

    let api = Router::new()
        .merge(auth::depts::router(ctx.clone()))
        .merge(items::depts::router(ctx.clone(), conn.clone()))
        .merge(categories::depts::router(ctx.clone(), conn.clone()))
        .merge(state::depts::router(ctx.clone(), conn.clone()))
        .merge(catalog::depts::router(ctx.clone(), conn.clone()))
        .merge(orders::depts::router(ctx, conn));

    let app = Router::new()
        .route("/", get(index))
        .route("/health", get(health))
        .nest("/api", api)
        .layer(TraceLayer::new_for_http());

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

    fn project_info_app() -> Router {
        Router::new().route("/", get(index)).route("/health", get(health))
    }

    #[tokio::test]
    async fn test_index_returns_project_info() {
        let app = project_info_app();
        let server = TestServer::new(app).unwrap();

        let response = server.get("/").await;
        response.assert_status(StatusCode::OK);

        let body: ProjectInfo = response.json();
        assert_eq!(body.project, "rust-axum-ddd-skel");
        assert_eq!(body.framework, "Axum");
    }

    #[tokio::test]
    async fn test_health_endpoint() {
        let app = project_info_app();
        let server = TestServer::new(app).unwrap();

        let response = server.get("/health").await;
        response.assert_status(StatusCode::OK);

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
    }
}
