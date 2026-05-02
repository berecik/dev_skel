//! `CatalogRepository` — storage abstraction for catalog items.

use async_trait::async_trait;

use crate::shared::DomainError;

pub use crate::entities::catalog_item::Model as CatalogItem;

#[derive(Debug, Clone)]
pub struct NewCatalogItem {
    pub name: String,
    pub description: String,
    pub price: f64,
    pub category: String,
    pub available: bool,
}

#[async_trait]
pub trait CatalogRepository: Send + Sync {
    async fn list(&self) -> Result<Vec<CatalogItem>, DomainError>;
    async fn get(&self, id: i32) -> Result<CatalogItem, DomainError>;
    async fn create(&self, new: NewCatalogItem) -> Result<CatalogItem, DomainError>;
}
