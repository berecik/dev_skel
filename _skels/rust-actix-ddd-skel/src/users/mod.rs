//! Users resource — repository + adapter only, no public routes.
//!
//! Mirrors `_skels/go-skel/internal/users/`. The auth + seed flows
//! depend on the `UserRepository` trait so they never touch
//! `DatabaseConnection` directly. There are no `routes.rs` /
//! `service.rs` here because user account management is exposed via
//! `/api/auth/*` (see the `auth` module), not as a CRUD resource.

pub mod adapters;
pub mod repository;

pub use adapters::sql::SeaUserRepository;
pub use repository::UserRepository;
