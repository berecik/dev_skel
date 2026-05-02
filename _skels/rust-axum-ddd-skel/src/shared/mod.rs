//! Cross-resource abstractions: domain errors, the abstract
//! `Repository` / `UnitOfWork` traits, shared HTTP helpers, and the
//! per-router `AppContext` that carries `Config` + the boxed
//! `UserRepository` into every resource's router so `AuthUser` can
//! extract from any subrouter state.
//!
//! Mirrors `_skels/rust-actix-ddd-skel/src/shared/`. Every per-resource
//! module (items, categories, orders, catalog, state, users, auth)
//! imports from here so the pattern is uniform across the skeleton.

pub mod context;
pub mod errors;
pub mod httpx;
pub mod repository;

pub use context::AppContext;
pub use errors::DomainError;
pub use httpx::ApiError;
#[allow(unused_imports)]
pub use repository::{AbstractUnitOfWork, Repository};
