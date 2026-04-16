//! Rust/Actix-web Skeleton Project
//!
//! Wires the wrapper-shared backend stack so the React frontend's
//! `/api/auth/*`, `/api/items`, and `/api/state` calls work
//! out-of-the-box. The schema mirrors the django-bolt skel so a
//! single `_shared/db.sqlite3` is interchangeable between backends.

mod auth;
mod config;
mod db;
mod error;
mod handlers;

use actix_web::{get, web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use tracing_actix_web::TracingLogger;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};

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
        project: "rust-actix-skel".to_string(),
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
    // Load wrapper-shared `.env` first then the local one (idempotent
    // when nothing is present — keeps the skeleton runnable on a bare
    // clone).
    load_dotenv();

    let cfg = Config::from_env();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rust_actix_skel=debug,actix_web=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_addr = format!("{}:{}", cfg.service_host, cfg.service_port);
    tracing::info!(
        target: "rust_actix_skel",
        database_url = %cfg.database_url,
        jwt_issuer = %cfg.jwt_issuer,
        bind = %bind_addr,
        "starting Actix server with wrapper-shared config",
    );

    // Connect + bootstrap schema before binding the listener so a bad
    // DB URL fails fast instead of returning 500s on every request.
    let pool = db::connect_and_init(&cfg.database_url).await.map_err(|e| {
        tracing::error!(error = ?e, "failed to connect / init database");
        std::io::Error::other(format!("database init failed: {e}"))
    })?;

    let cfg_data = web::Data::new(cfg.clone());
    let pool_data = web::Data::new(pool);

    HttpServer::new(move || {
        App::new()
            .wrap(TracingLogger::default())
            .app_data(cfg_data.clone())
            .app_data(pool_data.clone())
            .service(index)
            .service(health)
            .configure(handlers::register)
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
        assert_eq!(body.project, "rust-actix-skel");
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
