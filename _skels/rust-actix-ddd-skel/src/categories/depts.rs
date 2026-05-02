//! Composition seam for the `categories` resource.

use std::sync::Arc;

use actix_web::web;
use sea_orm::DatabaseConnection;

use crate::categories::adapters::sql::SeaCategoryRepository;
use crate::categories::repository::CategoryRepository;
use crate::categories::routes::{
    create_category, delete_category, get_category, list_categories, update_category,
};
use crate::categories::service::CategoriesService;
use crate::items::adapters::sql::SeaItemRepository;
use crate::items::repository::ItemRepository;

/// Mount `/categories` under the caller's parent scope.
pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {
    let cat_repo: Arc<dyn CategoryRepository> = Arc::new(SeaCategoryRepository::new(conn.clone()));
    let item_repo: Arc<dyn ItemRepository> = Arc::new(SeaItemRepository::new(conn));
    let svc = CategoriesService::new(cat_repo, item_repo);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/categories")
            .service(list_categories)
            .service(create_category)
            .service(get_category)
            .service(update_category)
            .service(delete_category),
    );
}
