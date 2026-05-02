//! Cross-resource abstractions: domain errors, the abstract
//! `Repository` / `UnitOfWork` traits, and shared HTTP helpers.
//!
//! Mirrors `_skels/go-skel/internal/shared/` and the FastAPI pilot's
//! `app/core/`. Every per-resource module (items, categories, orders,
//! catalog, state, users, auth) imports from here so the pattern is
//! uniform across the skeleton.

pub mod errors;
pub mod httpx;
pub mod repository;

pub use errors::DomainError;
#[allow(unused_imports)]
pub use repository::{AbstractUnitOfWork, Repository};
