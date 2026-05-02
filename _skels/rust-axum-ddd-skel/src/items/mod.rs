//! Items resource — `/api/items`. Canonical CRUD example.
//!
//! Each layer owns one concern:
//! * `repository` — abstract `ItemRepository` trait.
//! * `adapters::sql` — SeaORM-backed `SeaItemRepository`.
//! * `service` — `ItemsService` with CRUD + `complete`.
//! * `routes` — axum handlers that translate `DomainError` into HTTP
//!   via the `IntoResponse` impl on `ApiError`.
//! * `depts` — `router(ctx) -> Router` composition seam.

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

#[allow(unused_imports)]
pub use depts::router;
#[allow(unused_imports)]
pub use repository::{ItemRepository, NewItem};
#[allow(unused_imports)]
pub use service::{ItemsService, NewItemDTO};
