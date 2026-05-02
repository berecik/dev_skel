//! Composition seam for the `auth` resource.
//!
//! `router(ctx)` builds an `AuthService` over the `AppContext`'s
//! `UserRepository`, bakes it into the per-resource state, and
//! returns a `Router` mounted at `/auth/{register, login}`.

use std::sync::Arc;

use axum::{
    extract::FromRef,
    routing::post,
    Router,
};

use crate::auth::routes::{login_handler, register_handler};
use crate::auth::service::AuthService;
use crate::shared::AppContext;

/// Router state for the auth subrouter. Login + register only need
/// the `AuthService`; we don't bother carrying `AppContext` here
/// because the auth handlers do not extract `AuthUser` (they MINT
/// tokens; they don't validate them).
#[derive(Clone)]
pub struct AuthRouterState {
    pub service: Arc<AuthService>,
}

impl FromRef<AuthRouterState> for Arc<AuthService> {
    fn from_ref(input: &AuthRouterState) -> Self {
        input.service.clone()
    }
}

/// Build the `/auth` subrouter. `ctx` carries `Config` +
/// `UserRepository` — we use them to construct the `AuthService`.
pub fn router(ctx: AppContext) -> Router {
    let service = Arc::new(AuthService::new(ctx.config, ctx.user_repo));
    let state = AuthRouterState { service };
    Router::new()
        .route("/auth/register", post(register_handler))
        .route("/auth/login", post(login_handler))
        .with_state(state)
}
