//! Service-layer logic for `/api/items`. Holds an `Arc<dyn
//! ItemRepository>` — never a `DatabaseConnection`.

use std::sync::Arc;

use crate::items::repository::{Item, ItemRepository, NewItem};
use crate::shared::DomainError;

/// Input shape for `create`. Separate from the entity so the route's
/// payload type and the service's input shape are decoupled.
#[derive(Debug, Clone)]
pub struct NewItemDTO {
    pub name: String,
    pub description: Option<String>,
    pub is_completed: bool,
    pub category_id: Option<i32>,
}

/// Coordinates `ItemRepository` for HTTP routes.
#[derive(Clone)]
pub struct ItemsService {
    repo: Arc<dyn ItemRepository>,
}

impl ItemsService {
    pub fn new(repo: Arc<dyn ItemRepository>) -> Self {
        Self { repo }
    }

    pub async fn list(&self) -> Result<Vec<Item>, DomainError> {
        self.repo.list().await
    }

    pub async fn get(&self, id: i32) -> Result<Item, DomainError> {
        self.repo.get(id).await
    }

    pub async fn create(&self, dto: NewItemDTO) -> Result<Item, DomainError> {
        if dto.name.trim().is_empty() {
            return Err(DomainError::Validation(
                "item name cannot be empty".to_string(),
            ));
        }
        self.repo
            .create(NewItem {
                name: dto.name,
                description: dto.description,
                is_completed: dto.is_completed,
                category_id: dto.category_id,
            })
            .await
    }

    pub async fn complete(&self, id: i32) -> Result<Item, DomainError> {
        self.repo.complete(id).await
    }
}
