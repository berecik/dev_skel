//! Composition seam for the `orders` resource.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::{delete, get, post, put},
    Router,
};
use sea_orm::DatabaseConnection;

use crate::catalog;
use crate::orders::adapters::sql::SeaOrderRepository;
use crate::orders::repository::OrderRepository;
use crate::orders::routes::{
    add_order_line, approve_order, create_order, delete_order, get_order, list_orders,
    reject_order, remove_order_line, set_order_address, submit_order,
};
use crate::orders::service::OrdersService;
use crate::shared::AppContext;

#[derive(Clone)]
pub struct OrdersRouterState {
    pub service: Arc<OrdersService>,
    pub ctx: AppContext,
}

impl FromRef<OrdersRouterState> for Arc<OrdersService> {
    fn from_ref(input: &OrdersRouterState) -> Self {
        input.service.clone()
    }
}

impl FromRef<OrdersRouterState> for AppContext {
    fn from_ref(input: &OrdersRouterState) -> Self {
        input.ctx.clone()
    }
}

pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router {
    let repo: Arc<dyn OrderRepository> = Arc::new(SeaOrderRepository::new(conn.clone()));
    let catalog_svc = catalog::depts::build_service(conn);
    let service = Arc::new(OrdersService::new(repo, catalog_svc));
    let state = OrdersRouterState { service, ctx };
    Router::new()
        .route("/orders", get(list_orders).post(create_order))
        .route("/orders/:id", get(get_order).delete(delete_order))
        .route("/orders/:id/lines", post(add_order_line))
        .route("/orders/:id/lines/:line_id", delete(remove_order_line))
        .route("/orders/:id/address", put(set_order_address))
        .route("/orders/:id/submit", post(submit_order))
        .route("/orders/:id/approve", post(approve_order))
        .route("/orders/:id/reject", post(reject_order))
        .with_state(state)
}
