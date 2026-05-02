//! Composition seam for the `state` resource.

use std::sync::Arc;

use actix_web::web;
use sea_orm::DatabaseConnection;

use crate::state::adapters::sql::SeaStateRepository;
use crate::state::repository::StateRepository;
use crate::state::routes::{delete_state, list_state, upsert_state};
use crate::state::service::StateService;

pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {
    let repo: Arc<dyn StateRepository> = Arc::new(SeaStateRepository::new(conn));
    let svc = StateService::new(repo);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/state")
            .service(list_state)
            .service(upsert_state)
            .service(delete_state),
    );
}
