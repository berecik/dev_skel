//! `CategoryRepository` — storage abstraction for categories.

use async_trait::async_trait;

use crate::shared::DomainError;

pub use crate::entities::category::Model as Category;

#[derive(Debug, Clone)]
pub struct NewCategory {
    pub name: String,
    pub description: Option<String>,
}

#[async_trait]
pub trait CategoryRepository: Send + Sync {
    async fn list(&self) -> Result<Vec<Category>, DomainError>;
    async fn get(&self, id: i32) -> Result<Category, DomainError>;
    async fn create(&self, new: NewCategory) -> Result<Category, DomainError>;
    async fn update(&self, id: i32, new: NewCategory) -> Result<Category, DomainError>;
    async fn delete(&self, id: i32) -> Result<(), DomainError>;
}
