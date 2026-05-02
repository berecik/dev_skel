//! Composition seam for the `state` resource.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::get,
    Router,
};
use sea_orm::DatabaseConnection;

use crate::shared::AppContext;
use crate::state::adapters::sql::SeaStateRepository;
use crate::state::repository::StateRepository;
use crate::state::routes::{delete_state, list_state, upsert_state};
use crate::state::service::StateService;

#[derive(Clone)]
pub struct StateRouterState {
    pub service: Arc<StateService>,
    pub ctx: AppContext,
}

impl FromRef<StateRouterState> for Arc<StateService> {
    fn from_ref(input: &StateRouterState) -> Self {
        input.service.clone()
    }
}

impl FromRef<StateRouterState> for AppContext {
    fn from_ref(input: &StateRouterState) -> Self {
        input.ctx.clone()
    }
}

pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router {
    let repo: Arc<dyn StateRepository> = Arc::new(SeaStateRepository::new(conn));
    let service = Arc::new(StateService::new(repo));
    let state = StateRouterState { service, ctx };
    Router::new()
        .route("/state", get(list_state))
        .route(
            "/state/:key",
            axum::routing::put(upsert_state).delete(delete_state),
        )
        .with_state(state)
}
