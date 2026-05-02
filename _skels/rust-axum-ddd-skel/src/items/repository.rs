//! `ItemRepository` — storage abstraction for the items resource.

use async_trait::async_trait;

use crate::shared::DomainError;

/// We expose the SeaORM model as the entity type. The repository
/// interface protects callers from `DatabaseConnection`, not from
/// the column layout.
pub use crate::entities::item::Model as Item;

/// Insert payload for the items repository.
#[derive(Debug, Clone)]
pub struct NewItem {
    pub name: String,
    pub description: Option<String>,
    pub is_completed: bool,
    pub category_id: Option<i32>,
}

#[async_trait]
pub trait ItemRepository: Send + Sync {
    async fn list(&self) -> Result<Vec<Item>, DomainError>;
    async fn get(&self, id: i32) -> Result<Item, DomainError>;
    async fn create(&self, new: NewItem) -> Result<Item, DomainError>;
    /// Flip `is_completed=true` and return the refreshed row.
    /// Idempotent.
    async fn complete(&self, id: i32) -> Result<Item, DomainError>;
    /// Set `category_id = NULL` for every item that points at the
    /// supplied category. Used by `categories::CategoriesService::delete`
    /// to preserve the prior `ON DELETE SET NULL` semantic across
    /// SeaORM-backed Postgres deployments where the entity-declared
    /// FK does the same thing automatically — calling this is
    /// idempotent and safe in both cases.
    async fn clear_category(&self, category_id: i32) -> Result<(), DomainError>;
}
