//! Composition seam for the `orders` resource.

use std::sync::Arc;

use actix_web::web;
use sea_orm::DatabaseConnection;

use crate::catalog;
use crate::orders::adapters::sql::SeaOrderRepository;
use crate::orders::repository::OrderRepository;
use crate::orders::routes::{
    add_order_line, approve_order, create_order, delete_order, get_order, list_orders,
    reject_order, remove_order_line, set_order_address, submit_order,
};
use crate::orders::service::OrdersService;

pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {
    let repo: Arc<dyn OrderRepository> = Arc::new(SeaOrderRepository::new(conn.clone()));
    let catalog_svc = catalog::depts::build_service(conn);
    let svc = OrdersService::new(repo, catalog_svc);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/orders")
            .service(create_order)
            .service(list_orders)
            .service(get_order)
            .service(add_order_line)
            .service(remove_order_line)
            .service(set_order_address)
            .service(submit_order)
            .service(approve_order)
            .service(reject_order)
            .service(delete_order),
    );
}
