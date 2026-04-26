//! HTTP handlers, grouped by resource.
//!
//! Routes are registered in `main.rs` via `App::configure(register)`
//! so the wiring lives in one place and the per-module functions can
//! stay focused on a single resource.

pub mod auth;
pub mod categories;
pub mod items;
pub mod orders;
pub mod state;

use actix_web::web;

/// Mount every wrapper-shared route under `/api/...`. Called from
/// `main.rs` so a single `App::configure(handlers::register)` line
/// wires the entire backend.
pub fn register(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api")
            .service(
                web::scope("/auth")
                    .service(auth::register_handler)
                    .service(auth::login_handler),
            )
            .service(
                web::scope("/categories")
                    .service(categories::list_categories)
                    .service(categories::create_category)
                    .service(categories::get_category)
                    .service(categories::update_category)
                    .service(categories::delete_category),
            )
            .service(
                web::scope("/items")
                    .service(items::list_items)
                    .service(items::create_item)
                    .service(items::get_item)
                    .service(items::complete_item),
            )
            .service(
                web::scope("/state")
                    .service(state::list_state)
                    .service(state::upsert_state)
                    .service(state::delete_state),
            )
            .service(
                web::scope("/catalog")
                    .service(orders::list_catalog)
                    .service(orders::create_catalog_item)
                    .service(orders::get_catalog_item),
            )
            .service(
                web::scope("/orders")
                    .service(orders::create_order)
                    .service(orders::list_orders)
                    .service(orders::get_order)
                    .service(orders::add_order_line)
                    .service(orders::remove_order_line)
                    .service(orders::set_order_address)
                    .service(orders::submit_order)
                    .service(orders::approve_order)
                    .service(orders::reject_order)
                    .service(orders::delete_order),
            ),
    );
}
