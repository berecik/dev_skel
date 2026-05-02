//! `OrderRepository` — orders aggregate persistence abstraction.
//!
//! The service composes operations across orders, lines, and
//! addresses via this single interface so all the SeaORM details
//! live in one adapter. `OrdersUnitOfWork` is declared for future
//! transactional needs; today the SeaORM adapter implements
//! `OrderRepository` directly without an explicit tx scope.

use async_trait::async_trait;
use chrono::{DateTime, Utc};

use crate::shared::DomainError;

pub use crate::entities::order::Model as Order;
pub use crate::entities::order_address::Model as OrderAddress;
pub use crate::entities::order_line::Model as OrderLine;

/// Insert payload for `create_line`.
#[derive(Debug, Clone)]
pub struct AddLine {
    pub order_id: i32,
    pub catalog_item_id: i32,
    pub quantity: i32,
    pub unit_price: f64,
}

/// Insert / update payload for `upsert_address`.
#[derive(Debug, Clone)]
pub struct NewAddress {
    pub street: String,
    pub city: String,
    pub zip_code: String,
    pub phone: String,
    pub notes: String,
}

/// Status / metadata patch applied by submit / approve / reject.
#[derive(Debug, Clone, Default)]
pub struct OrderStatusUpdate {
    pub status: String,
    pub submitted_at: Option<Option<DateTime<Utc>>>,
    pub wait_minutes: Option<Option<i32>>,
    pub feedback: Option<Option<String>>,
}

#[async_trait]
pub trait OrderRepository: Send + Sync {
    // ----- Order -----
    async fn create_order(&self, user_id: i32) -> Result<Order, DomainError>;
    async fn get_order(&self, id: i32) -> Result<Order, DomainError>;
    async fn list_orders_for_user(&self, user_id: i32) -> Result<Vec<Order>, DomainError>;
    async fn apply_status_update(
        &self,
        id: i32,
        update: OrderStatusUpdate,
    ) -> Result<Order, DomainError>;
    async fn delete_order(&self, id: i32) -> Result<(), DomainError>;

    // ----- Lines -----
    async fn create_line(&self, payload: AddLine) -> Result<OrderLine, DomainError>;
    async fn list_lines_for_order(&self, order_id: i32) -> Result<Vec<OrderLine>, DomainError>;
    async fn count_lines_for_order(&self, order_id: i32) -> Result<u64, DomainError>;
    /// Returns the rows-affected count so callers can tell apart
    /// "missing" from "deleted".
    async fn delete_line(&self, order_id: i32, line_id: i32) -> Result<u64, DomainError>;
    async fn delete_lines_for_order(&self, order_id: i32) -> Result<(), DomainError>;

    // ----- Address -----
    async fn get_address_for_order(
        &self,
        order_id: i32,
    ) -> Result<Option<OrderAddress>, DomainError>;
    async fn upsert_address(
        &self,
        order_id: i32,
        payload: NewAddress,
    ) -> Result<OrderAddress, DomainError>;
    async fn delete_addresses_for_order(&self, order_id: i32) -> Result<(), DomainError>;
}

/// Marker trait for a future transactional scope around the orders
/// aggregate. Mirrors the FastAPI pilot's `AbstractUnitOfWork`.
/// The current SeaORM-backed adapter does not implement this — it
/// is declared here so resources that need transactional writes
/// can opt in without churning the service signatures.
#[allow(dead_code)]
#[async_trait]
pub trait OrdersUnitOfWork: Send + Sync {
    async fn commit(&mut self) -> Result<(), DomainError>;
    async fn rollback(&mut self) -> Result<(), DomainError>;
}
