//! Composition seam for the `items` resource. `router` wires a
//! `SeaItemRepository` into an `ItemsService`, bakes them into a
//! per-resource state, and returns a `Router` mounted at `/items`.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::{get, post},
    Router,
};
use sea_orm::DatabaseConnection;

use crate::items::adapters::sql::SeaItemRepository;
use crate::items::repository::ItemRepository;
use crate::items::routes::{complete_item, create_item, get_item, list_items};
use crate::items::service::ItemsService;
use crate::shared::AppContext;

/// Router state for the items subrouter. Carries the service plus the
/// shared `AppContext` so handlers that ask for `AuthUser` can extract
/// it via `FromRef<ItemsRouterState> for AppContext`.
#[derive(Clone)]
pub struct ItemsRouterState {
    pub service: Arc<ItemsService>,
    pub ctx: AppContext,
}

impl FromRef<ItemsRouterState> for Arc<ItemsService> {
    fn from_ref(input: &ItemsRouterState) -> Self {
        input.service.clone()
    }
}

impl FromRef<ItemsRouterState> for AppContext {
    fn from_ref(input: &ItemsRouterState) -> Self {
        input.ctx.clone()
    }
}

/// Build a default `ItemsService` from a shared `DatabaseConnection`.
/// Other compositions (e.g. category cascade reuses this service)
/// can call `ItemsService::new` directly with their own repo.
pub fn build_service(conn: Arc<DatabaseConnection>) -> ItemsService {
    let repo: Arc<dyn ItemRepository> = Arc::new(SeaItemRepository::new(conn));
    ItemsService::new(repo)
}

/// Build the `/items` subrouter.
pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router {
    let service = Arc::new(build_service(conn));
    let state = ItemsRouterState { service, ctx };
    Router::new()
        .route("/items", get(list_items).post(create_item))
        .route("/items/:id", get(get_item))
        .route("/items/:id/complete", post(complete_item))
        .with_state(state)
}
