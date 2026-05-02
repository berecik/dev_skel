//! Composition seam for the `auth` resource.
//!
//! `register_routes` builds an `AuthService` over the supplied
//! `UserRepository`, registers it via `app_data`, and mounts the
//! `/api/auth/*` scope.

use std::sync::Arc;

use actix_web::web;

use crate::auth::routes::{login_handler, register_handler};
use crate::auth::service::AuthService;
use crate::config::Config;
use crate::users::UserRepository;

/// Mount `/api/auth/{register, login}`.
///
/// Note that `AuthService` does NOT need to be re-registered if it
/// was already supplied via `app_data` upstream — but the canonical
/// composition is to call `register_routes` exactly once per app.
pub fn register_routes(
    cfg: &mut web::ServiceConfig,
    config: Config,
    users: Arc<dyn UserRepository>,
) {
    let svc = AuthService::new(config, users);
    cfg.app_data(web::Data::new(svc)).service(
        web::scope("/auth")
            .service(register_handler)
            .service(login_handler),
    );
}
