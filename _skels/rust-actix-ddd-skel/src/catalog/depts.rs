//! Composition seam for the `catalog` resource.

use std::sync::Arc;

use actix_web::web;
use sea_orm::DatabaseConnection;

use crate::catalog::adapters::sql::SeaCatalogRepository;
use crate::catalog::repository::CatalogRepository;
use crate::catalog::routes::{create_catalog_item, get_catalog_item, list_catalog};
use crate::catalog::service::CatalogService;

/// Build a default `CatalogService`. Other modules (orders) reuse
/// the same service via this helper instead of constructing their
/// own adapter.
pub fn build_service(conn: Arc<DatabaseConnection>) -> CatalogService {
    let repo: Arc<dyn CatalogRepository> = Arc::new(SeaCatalogRepository::new(conn));
    CatalogService::new(repo)
}

pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {
    let svc = build_service(conn);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/catalog")
            .service(list_catalog)
            .service(create_catalog_item)
            .service(get_catalog_item),
    );
}
