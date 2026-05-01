//! HTTP handlers, grouped by resource.
//!
//! Routes are assembled into one `Router` by `wrapper_router()` so the
//! main entrypoint can stay focused on bind / serve concerns.

pub mod auth;
pub mod categories;
pub mod items;
pub mod orders;
pub mod state;

use std::sync::Arc;

use axum::{
    routing::{delete, get, post, put},
    Router,
};

use crate::AppState;

/// Build the wrapper-shared `/api/*` router. Mounted at `/` by
/// `main.rs` so URLs end up at `/api/auth/login`, `/api/items/{id}`,
/// `/api/categories/{id}`, `/api/catalog/{id}`,
/// `/api/orders/{id}`, `/api/state/{key}`, etc. — the contract
/// every dev_skel backend honours.
pub fn wrapper_router() -> Router<Arc<AppState>> {
    Router::new()
        // Auth
        .route("/api/auth/register", post(auth::register_handler))
        .route("/api/auth/login", post(auth::login_handler))
        // Categories
        .route(
            "/api/categories",
            get(categories::list_categories).post(categories::create_category),
        )
        .route(
            "/api/categories/:id",
            get(categories::get_category)
                .put(categories::update_category)
                .delete(categories::delete_category),
        )
        // Items
        .route("/api/items", get(items::list_items).post(items::create_item))
        .route("/api/items/:id", get(items::get_item))
        .route("/api/items/:id/complete", post(items::complete_item))
        // Catalog
        .route(
            "/api/catalog",
            get(orders::list_catalog).post(orders::create_catalog_item),
        )
        .route("/api/catalog/:id", get(orders::get_catalog_item))
        // Orders
        .route(
            "/api/orders",
            get(orders::list_orders).post(orders::create_order),
        )
        .route(
            "/api/orders/:id",
            get(orders::get_order).delete(orders::delete_order),
        )
        .route(
            "/api/orders/:order_id/lines",
            post(orders::add_order_line),
        )
        .route(
            "/api/orders/:order_id/lines/:line_id",
            delete(orders::remove_order_line),
        )
        .route(
            "/api/orders/:order_id/address",
            put(orders::set_order_address),
        )
        .route("/api/orders/:order_id/submit", post(orders::submit_order))
        .route("/api/orders/:order_id/approve", post(orders::approve_order))
        .route("/api/orders/:order_id/reject", post(orders::reject_order))
        // State
        .route("/api/state", get(state::list_state))
        .route(
            "/api/state/:key",
            put(state::upsert_state).delete(state::delete_state),
        )
}
