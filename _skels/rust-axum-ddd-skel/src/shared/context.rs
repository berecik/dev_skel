//! `AppContext` — shared composition handle injected into every
//! per-resource `depts::router(ctx)` so handlers can extract the
//! authenticated user.
//!
//! In actix-ddd this same data is registered into `app_data` and the
//! `AuthUser` extractor pulls it back out per request. axum prefers
//! statically-typed router state, so we expose `AppContext` as a
//! `Clone`-able struct and require every per-resource `RouterState`
//! to provide a `FromRef<RouterState> for AppContext` impl. The
//! `AuthUser` extractor extracts the context generically over `S`
//! using that bound.

use std::sync::Arc;

use crate::config::Config;
use crate::users::UserRepository;

/// Composition handle that the auth extractor reaches for via
/// `FromRef<S, AppContext>`. Resource-specific router states embed
/// this so `AuthUser` can be requested by any handler regardless of
/// which resource it belongs to.
#[derive(Clone)]
pub struct AppContext {
    pub config: Config,
    pub user_repo: Arc<dyn UserRepository>,
}

impl AppContext {
    pub fn new(config: Config, user_repo: Arc<dyn UserRepository>) -> Self {
        Self { config, user_repo }
    }
}
