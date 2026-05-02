//! Rust/Actix-web Skeleton Project
//!
//! Wires the wrapper-shared backend stack so the React frontend's
//! `/api/auth/*`, `/api/categories`, `/api/items`, `/api/state`,
//! `/api/catalog`, and `/api/orders` calls work out-of-the-box.
//!
//! Resources are organised as light-DDD layers under `src/`:
//! each resource (items, categories, orders, catalog, state, users,
//! auth) owns a `Repository` trait, an adapter implementing it via
//! SeaORM, a `Service`, a `routes.rs` that wires HTTP to the
//! service, and a `depts.rs` that composes them. `main.rs`'s job is
//! just to compose them.

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

use std::sync::Arc;

use actix_web::{get, web, App, HttpResponse, HttpServer, Responder};
use sea_orm::DatabaseConnection;
use serde::{Deserialize, Serialize};
use tracing_actix_web::TracingLogger;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};
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

#[get("/")]
async fn index(cfg: web::Data<Config>) -> impl Responder {
    HttpResponse::Ok().json(ProjectInfo {
        project: "rust-actix-ddd-skel".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        framework: "Actix-web".to_string(),
        status: format!("running (issuer={})", cfg.jwt_issuer),
    })
}

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json(HealthResponse {
        status: "healthy".to_string(),
    })
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Load wrapper-shared `.env` first then the local one.
    load_dotenv();

    let cfg = Config::from_env();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rust_actix_ddd_skel=debug,actix_web=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_addr = format!("{}:{}", cfg.service_host, cfg.service_port);
    tracing::info!(
        target: "rust_actix_ddd_skel",
        database_url = %cfg.database_url,
        jwt_issuer = %cfg.jwt_issuer,
        bind = %bind_addr,
        "starting Actix server with wrapper-shared config",
    );

    // Connect + bootstrap schema before binding the listener so a bad
    // DB URL fails fast instead of returning 500s on every request.
    let conn = db::connect_and_init(&cfg.database_url).await.map_err(|e| {
        tracing::error!(error = ?e, "failed to connect / init database");
        std::io::Error::other(format!("database init failed: {e}"))
    })?;
    let conn = Arc::new(conn);

    // Build the user repository once and share it: seed, the auth
    // service, and the JWT extractor all reach for the same handle.
    let user_repo: Arc<dyn UserRepository> =
        Arc::new(users::SeaUserRepository::new(conn.clone()));

    seed::seed_default_accounts(user_repo.clone())
        .await
        .map_err(|e| {
            tracing::error!(error = ?e, "failed to seed default accounts");
            std::io::Error::other(format!("seed failed: {e}"))
        })?;

    let cfg_for_app = cfg.clone();
    let cfg_data = web::Data::new(cfg.clone());
    let conn_data: web::Data<DatabaseConnection> = web::Data::from(conn.clone());
    let user_repo_data = web::Data::new(user_repo.clone());

    HttpServer::new(move || {
        let conn = conn.clone();
        let cfg_inner = cfg_for_app.clone();
        let user_repo = user_repo.clone();
        App::new()
            .wrap(TracingLogger::default())
            // Shared app_data — the JWT extractor reaches for both
            // Config and the boxed UserRepository.
            .app_data(cfg_data.clone())
            .app_data(conn_data.clone())
            .app_data(user_repo_data.clone())
            .service(index)
            .service(health)
            .service(
                web::scope("/api")
                    .configure(move |c| {
                        auth::register_routes(c, cfg_inner.clone(), user_repo.clone())
                    })
                    .configure(|c| categories::register_routes(c, conn.clone()))
                    .configure(|c| items::register_routes(c, conn.clone()))
                    .configure(|c| state::register_routes(c, conn.clone()))
                    .configure(|c| catalog::register_routes(c, conn.clone()))
                    .configure(|c| orders::register_routes(c, conn.clone())),
            )
    })
    .bind(&bind_addr)?
    .run()
    .await
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::{test, App};

    fn project_info_app() -> App<
        impl actix_web::dev::ServiceFactory<
            actix_web::dev::ServiceRequest,
            Response = actix_web::dev::ServiceResponse,
            Config = (),
            InitError = (),
            Error = actix_web::Error,
        >,
    > {
        let cfg = Config::from_env();
        App::new()
            .app_data(web::Data::new(cfg))
            .service(index)
            .service(health)
    }

    #[actix_rt::test]
    async fn test_index_returns_project_info() {
        let app = test::init_service(project_info_app()).await;
        let req = test::TestRequest::get().uri("/").to_request();
        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());
        let body: ProjectInfo = test::read_body_json(resp).await;
        assert_eq!(body.project, "rust-actix-ddd-skel");
        assert_eq!(body.framework, "Actix-web");
    }

    #[actix_rt::test]
    async fn test_health_endpoint() {
        let app = test::init_service(project_info_app()).await;
        let req = test::TestRequest::get().uri("/health").to_request();
        let resp = test::call_service(&app, req).await;
        assert!(resp.status().is_success());
        let body: HealthResponse = test::read_body_json(resp).await;
        assert_eq!(body.status, "healthy");
    }
}
