//! Catalog resource — `/api/catalog`. Public browse surface (GET is
//! unauthenticated, POST + GET-by-id require a Bearer JWT).

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

#[allow(unused_imports)]
pub use depts::router;
#[allow(unused_imports)]
pub use repository::{CatalogRepository, NewCatalogItem};
#[allow(unused_imports)]
pub use service::{CatalogService, NewCatalogItemDTO};
