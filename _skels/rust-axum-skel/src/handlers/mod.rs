//! HTTP handlers, grouped by resource.
//!
//! Routes are assembled into one `Router` by `wrapper_router()` so the
//! main entrypoint can stay focused on bind / serve concerns.

pub mod auth;
pub mod categories;
pub mod items;
pub mod state;

use std::sync::Arc;

use axum::{
    routing::{get, post, put},
    Router,
};

use crate::AppState;

/// Build the wrapper-shared `/api/*` router. Mounted at `/` by
/// `main.rs` so URLs end up at `/api/auth/login`, `/api/items/{id}`,
/// `/api/categories/{id}`, `/api/state/{key}`, etc. — the contract
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
        // State
        .route("/api/state", get(state::list_state))
        .route(
            "/api/state/:key",
            put(state::upsert_state).delete(state::delete_state),
        )
}
