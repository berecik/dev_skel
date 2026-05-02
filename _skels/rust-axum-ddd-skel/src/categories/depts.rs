//! Composition seam for the `categories` resource.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::get,
    Router,
};
use sea_orm::DatabaseConnection;

use crate::categories::adapters::sql::SeaCategoryRepository;
use crate::categories::repository::CategoryRepository;
use crate::categories::routes::{
    create_category, delete_category, get_category, list_categories, update_category,
};
use crate::categories::service::CategoriesService;
use crate::items::adapters::sql::SeaItemRepository;
use crate::items::repository::ItemRepository;
use crate::shared::AppContext;

#[derive(Clone)]
pub struct CategoriesRouterState {
    pub service: Arc<CategoriesService>,
    pub ctx: AppContext,
}

impl FromRef<CategoriesRouterState> for Arc<CategoriesService> {
    fn from_ref(input: &CategoriesRouterState) -> Self {
        input.service.clone()
    }
}

impl FromRef<CategoriesRouterState> for AppContext {
    fn from_ref(input: &CategoriesRouterState) -> Self {
        input.ctx.clone()
    }
}

/// Build the `/categories` subrouter.
pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router {
    let cat_repo: Arc<dyn CategoryRepository> = Arc::new(SeaCategoryRepository::new(conn.clone()));
    let item_repo: Arc<dyn ItemRepository> = Arc::new(SeaItemRepository::new(conn));
    let service = Arc::new(CategoriesService::new(cat_repo, item_repo));
    let state = CategoriesRouterState { service, ctx };
    Router::new()
        .route("/categories", get(list_categories).post(create_category))
        .route(
            "/categories/:id",
            get(get_category).put(update_category).delete(delete_category),
        )
        .with_state(state)
}
