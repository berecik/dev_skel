//! Composition seam for the `catalog` resource.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::get,
    Router,
};
use sea_orm::DatabaseConnection;

use crate::catalog::adapters::sql::SeaCatalogRepository;
use crate::catalog::repository::CatalogRepository;
use crate::catalog::routes::{create_catalog_item, get_catalog_item, list_catalog};
use crate::catalog::service::CatalogService;
use crate::shared::AppContext;

#[derive(Clone)]
pub struct CatalogRouterState {
    pub service: Arc<CatalogService>,
    pub ctx: AppContext,
}

impl FromRef<CatalogRouterState> for Arc<CatalogService> {
    fn from_ref(input: &CatalogRouterState) -> Self {
        input.service.clone()
    }
}

impl FromRef<CatalogRouterState> for AppContext {
    fn from_ref(input: &CatalogRouterState) -> Self {
        input.ctx.clone()
    }
}

/// Build a default `CatalogService`. Other modules (orders) reuse
/// the same service via this helper instead of constructing their
/// own adapter.
pub fn build_service(conn: Arc<DatabaseConnection>) -> CatalogService {
    let repo: Arc<dyn CatalogRepository> = Arc::new(SeaCatalogRepository::new(conn));
    CatalogService::new(repo)
}

pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router {
    let service = Arc::new(build_service(conn));
    let state = CatalogRouterState { service, ctx };
    Router::new()
        .route("/catalog", get(list_catalog).post(create_catalog_item))
        .route("/catalog/:id", get(get_catalog_item))
        .with_state(state)
}
