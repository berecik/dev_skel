//! State resource — `/api/state`. Per-user JSON key/value store
//! backing the React `useAppState<T>(key, default)` hook.

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

pub use depts::register_routes;
#[allow(unused_imports)]
pub use repository::StateRepository;
#[allow(unused_imports)]
pub use service::StateService;
