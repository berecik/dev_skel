//! Categories resource — `/api/categories`. CRUD shape.
//!
//! On delete the service first clears `items.category_id` to null
//! (preserving the prior `ON DELETE SET NULL` semantic from the
//! handler-monolith era) and then deletes the category row, so the
//! end-to-end behaviour stays identical regardless of whether
//! SQLite's FK enforcement is enabled.

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

#[allow(unused_imports)]
pub use depts::router;
#[allow(unused_imports)]
pub use repository::{CategoryRepository, NewCategory};
#[allow(unused_imports)]
pub use service::{CategoriesService, NewCategoryDTO};
