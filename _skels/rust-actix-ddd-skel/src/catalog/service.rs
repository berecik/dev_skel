//! Service-layer logic for `/api/catalog`.

use std::sync::Arc;

use crate::catalog::repository::{CatalogItem, CatalogRepository, NewCatalogItem};
use crate::shared::DomainError;

#[derive(Debug, Clone)]
pub struct NewCatalogItemDTO {
    pub name: String,
    pub description: Option<String>,
    pub price: f64,
    pub category: Option<String>,
    pub available: bool,
}

#[derive(Clone)]
pub struct CatalogService {
    repo: Arc<dyn CatalogRepository>,
}

impl CatalogService {
    pub fn new(repo: Arc<dyn CatalogRepository>) -> Self {
        Self { repo }
    }

    pub async fn list(&self) -> Result<Vec<CatalogItem>, DomainError> {
        self.repo.list().await
    }

    pub async fn get(&self, id: i32) -> Result<CatalogItem, DomainError> {
        self.repo.get(id).await
    }

    pub async fn create(&self, dto: NewCatalogItemDTO) -> Result<CatalogItem, DomainError> {
        if dto.name.trim().is_empty() {
            return Err(DomainError::Validation(
                "catalog item name cannot be empty".to_string(),
            ));
        }
        if dto.price < 0.0 {
            return Err(DomainError::Validation(
                "price cannot be negative".to_string(),
            ));
        }
        self.repo
            .create(NewCatalogItem {
                name: dto.name,
                description: dto.description.unwrap_or_default(),
                price: dto.price,
                category: dto.category.unwrap_or_default(),
                available: dto.available,
            })
            .await
    }
}
