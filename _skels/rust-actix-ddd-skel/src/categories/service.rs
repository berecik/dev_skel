//! Service-layer logic for `/api/categories`.
//!
//! Holds two collaborators: a `CategoryRepository` and an
//! `ItemRepository`. The latter is used by `delete` to clear
//! `items.category_id` to NULL before the row is removed —
//! preserving the prior `ON DELETE SET NULL` semantic regardless of
//! whether the underlying SQLite has FK enforcement enabled. The
//! call is idempotent on Postgres where the entity-declared FK
//! cascade does the same thing on its own.

use std::sync::Arc;

use crate::categories::repository::{Category, CategoryRepository, NewCategory};
use crate::items::repository::ItemRepository;
use crate::shared::DomainError;

#[derive(Debug, Clone)]
pub struct NewCategoryDTO {
    pub name: String,
    pub description: Option<String>,
}

#[derive(Clone)]
pub struct CategoriesService {
    repo: Arc<dyn CategoryRepository>,
    items: Arc<dyn ItemRepository>,
}

impl CategoriesService {
    pub fn new(repo: Arc<dyn CategoryRepository>, items: Arc<dyn ItemRepository>) -> Self {
        Self { repo, items }
    }

    pub async fn list(&self) -> Result<Vec<Category>, DomainError> {
        self.repo.list().await
    }

    pub async fn get(&self, id: i32) -> Result<Category, DomainError> {
        self.repo.get(id).await
    }

    pub async fn create(&self, dto: NewCategoryDTO) -> Result<Category, DomainError> {
        if dto.name.trim().is_empty() {
            return Err(DomainError::Validation(
                "category name cannot be empty".to_string(),
            ));
        }
        self.repo
            .create(NewCategory {
                name: dto.name,
                description: dto.description,
            })
            .await
    }

    pub async fn update(&self, id: i32, dto: NewCategoryDTO) -> Result<Category, DomainError> {
        if dto.name.trim().is_empty() {
            return Err(DomainError::Validation(
                "category name cannot be empty".to_string(),
            ));
        }
        self.repo
            .update(
                id,
                NewCategory {
                    name: dto.name,
                    description: dto.description,
                },
            )
            .await
    }

    pub async fn delete(&self, id: i32) -> Result<(), DomainError> {
        // Make sure the row exists first so the response is 404 (not
        // 200) for missing categories.
        self.repo.get(id).await?;
        // Clear the FK on every item that pointed at this category
        // before the row goes away. Idempotent: when the underlying
        // FK already cascades (Postgres / SQLite-with-FKs-on) this
        // is a harmless no-op UPDATE.
        self.items.clear_category(id).await?;
        self.repo.delete(id).await
    }
}
