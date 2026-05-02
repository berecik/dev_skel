//! Orders resource — `/api/orders`. Aggregate (multi-table)
//! workflow: each state-mutating operation works on an `Order` plus
//! its `OrderLine` + `OrderAddress` children, and creating a line
//! reaches across to the `catalog` repository to snapshot the unit
//! price.
//!
//! The orders module declares its own `OrdersUnitOfWork` trait
//! analogously to the FastAPI pilot's `AbstractUnitOfWork`. Today
//! the SeaORM-backed implementation simply executes against the
//! shared `DatabaseConnection` (no explicit tx scope yet) — but the
//! seam is in place so a future implementation can begin / commit a
//! transaction without touching the service layer.

pub mod adapters;
pub mod depts;
pub mod repository;
pub mod routes;
pub mod service;

pub use depts::register_routes;
#[allow(unused_imports)]
pub use repository::{AddLine, NewAddress, OrderRepository, OrdersUnitOfWork};
#[allow(unused_imports)]
pub use service::{
    AddLineDTO, AddressDTO, ApproveDTO, OrderDetail, OrdersService, RejectDTO,
};
