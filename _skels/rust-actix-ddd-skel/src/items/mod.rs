//! Items resource — `/api/items`. Canonical CRUD example.
//!
//! Each layer owns one concern:
//! * `repository` — abstract `ItemRepository` trait.
//! * `adapters::sql` — SeaORM-backed `SeaItemRepository`.
//! * `service` — `ItemsService<R>` with CRUD + `complete`.
//! * `routes` — actix handlers that translate `DomainError` into
//!   HTTP via the shared `ResponseError` impl.
//! * `depts` — `register_routes(cfg, conn)` composition seam.

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

pub use depts::register_routes;
#[allow(unused_imports)]
pub use repository::{ItemRepository, NewItem};
#[allow(unused_imports)]
pub use service::{ItemsService, NewItemDTO};
