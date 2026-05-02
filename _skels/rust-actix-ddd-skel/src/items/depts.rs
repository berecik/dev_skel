//! Composition seam for the `items` resource. `register_routes`
//! wires a `SeaItemRepository` into an `ItemsService`, registers it
//! via `app_data`, and mounts `/items` under the parent scope.

use std::sync::Arc;

use actix_web::web;
use sea_orm::DatabaseConnection;

use crate::items::adapters::sql::SeaItemRepository;
use crate::items::repository::ItemRepository;
use crate::items::routes::{complete_item, create_item, get_item, list_items};
use crate::items::service::ItemsService;

/// Build a default `ItemsService` from a shared `DatabaseConnection`.
/// Other compositions (e.g. category cascade reuses this service)
/// can call `ItemsService::new` directly with their own repo.
pub fn build_service(conn: Arc<DatabaseConnection>) -> ItemsService {
    let repo: Arc<dyn ItemRepository> = Arc::new(SeaItemRepository::new(conn));
    ItemsService::new(repo)
}

/// Mount `/items` under the caller's parent scope.
pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {
    let svc = build_service(conn);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/items")
            .service(list_items)
            .service(create_item)
            .service(get_item)
            .service(complete_item),
    );
}
