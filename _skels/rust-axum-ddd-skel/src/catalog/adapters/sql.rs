//! SeaORM-backed implementation of `CatalogRepository`.

use std::sync::Arc;

use async_trait::async_trait;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait, QueryOrder, Set};

use crate::catalog::repository::{CatalogItem, CatalogRepository, NewCatalogItem};
use crate::entities::catalog_item;
use crate::shared::DomainError;

#[derive(Clone)]
pub struct SeaCatalogRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaCatalogRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl CatalogRepository for SeaCatalogRepository {
    async fn list(&self) -> Result<Vec<CatalogItem>, DomainError> {
        let rows = catalog_item::Entity::find()
            .order_by_asc(catalog_item::Column::Name)
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn get(&self, id: i32) -> Result<CatalogItem, DomainError> {
        let row = catalog_item::Entity::find_by_id(id)
            .one(self.db.as_ref())
            .await?;
        row.ok_or_else(|| DomainError::NotFound(format!("catalog item {id} not found")))
    }

    async fn create(&self, new: NewCatalogItem) -> Result<CatalogItem, DomainError> {
        let active = catalog_item::ActiveModel {
            name: Set(new.name),
            description: Set(new.description),
            price: Set(new.price),
            category: Set(new.category),
            available: Set(new.available),
            ..Default::default()
        };
        let inserted = active.insert(self.db.as_ref()).await?;
        Ok(inserted)
    }
}
