//! Rust/Actix-web Skeleton Project

mod config;

use actix_web::{get, web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing_actix_web::TracingLogger;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::config::{load_dotenv, Config};

/// Application state — holds the wrapper-shared `Config` so handlers can
/// pull it out of `web::Data` instead of re-reading the environment.
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
#[get("/")]
async fn index(state: web::Data<Arc<AppState>>) -> impl Responder {
    HttpResponse::Ok().json(ProjectInfo {
        project: state.project_name.clone(),
        version: state.version.clone(),
        framework: "Actix-web".to_string(),
        status: "running".to_string(),
    })
}

/// Health check endpoint
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

    let config = Config::from_env();

    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rust_actix_skel=debug,actix_web=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let bind_addr = format!("{}:{}", config.service_host, config.service_port);
    tracing::info!(
        target: "rust_actix_skel",
        database_url = %config.database_url,
        jwt_issuer = %config.jwt_issuer,
        bind = %bind_addr,
        "starting Actix server with wrapper-shared config",
    );

    let state = Arc::new(AppState {
        project_name: "rust-actix-skel".to_string(),
        version: "1.0.0".to_string(),
        config,
    });

    HttpServer::new(move || {
        App::new()
            .wrap(TracingLogger::default())
            .app_data(web::Data::new(state.clone()))
            .service(index)
            .service(health)
    })
    .bind(&bind_addr)?
    .run()
    .await
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::{test, App};

    fn create_test_app() -> App<
        impl actix_web::dev::ServiceFactory<
            actix_web::dev::ServiceRequest,
            Response = actix_web::dev::ServiceResponse,
            Config = (),
            InitError = (),
            Error = actix_web::Error,
        >,
    > {
        let state = Arc::new(AppState {
            project_name: "rust-actix-skel".to_string(),
            version: "1.0.0".to_string(),
            config: Config::from_env(),
        });

        App::new()
            .app_data(web::Data::new(state))
            .service(index)
            .service(health)
    }

    #[actix_rt::test]
    async fn test_index_returns_project_info() {
        let app = test::init_service(create_test_app()).await;
        let req = test::TestRequest::get().uri("/").to_request();
        let resp = test::call_service(&app, req).await;

        assert!(resp.status().is_success());

        let body: ProjectInfo = test::read_body_json(resp).await;
        assert_eq!(body.project, "rust-actix-skel");
        assert_eq!(body.framework, "Actix-web");
    }

    #[actix_rt::test]
    async fn test_health_endpoint() {
        let app = test::init_service(create_test_app()).await;
        let req = test::TestRequest::get().uri("/health").to_request();
        let resp = test::call_service(&app, req).await;

        assert!(resp.status().is_success());

        let body: HealthResponse = test::read_body_json(resp).await;
        assert_eq!(body.status, "healthy");
    }
}
