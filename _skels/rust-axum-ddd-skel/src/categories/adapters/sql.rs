//! SeaORM-backed implementation of `CategoryRepository`.

use std::sync::Arc;

use async_trait::async_trait;
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, DatabaseConnection, EntityTrait, ModelTrait, QueryOrder, Set,
};

use crate::categories::repository::{Category, CategoryRepository, NewCategory};
use crate::entities::category;
use crate::shared::{errors::is_unique_violation, DomainError};

#[derive(Clone)]
pub struct SeaCategoryRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaCategoryRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl CategoryRepository for SeaCategoryRepository {
    async fn list(&self) -> Result<Vec<Category>, DomainError> {
        let rows = category::Entity::find()
            .order_by_asc(category::Column::Name)
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn get(&self, id: i32) -> Result<Category, DomainError> {
        let row = category::Entity::find_by_id(id)
            .one(self.db.as_ref())
            .await?;
        row.ok_or_else(|| DomainError::NotFound(format!("category {id} not found")))
    }

    async fn create(&self, new: NewCategory) -> Result<Category, DomainError> {
        let now = Utc::now();
        let active = category::ActiveModel {
            name: Set(new.name.clone()),
            description: Set(new.description),
            created_at: Set(now),
            updated_at: Set(now),
            ..Default::default()
        };
        match active.insert(self.db.as_ref()).await {
            Ok(model) => Ok(model),
            Err(err) => {
                if is_unique_violation(&err) {
                    Err(DomainError::Conflict(format!(
                        "category '{}' already exists",
                        new.name
                    )))
                } else {
                    Err(DomainError::Db(err))
                }
            }
        }
    }

    async fn update(&self, id: i32, new: NewCategory) -> Result<Category, DomainError> {
        let row = category::Entity::find_by_id(id)
            .one(self.db.as_ref())
            .await?;
        let existing =
            row.ok_or_else(|| DomainError::NotFound(format!("category {id} not found")))?;
        let mut active: category::ActiveModel = existing.into();
        active.name = Set(new.name.clone());
        active.description = Set(new.description);
        active.updated_at = Set(Utc::now());
        match active.update(self.db.as_ref()).await {
            Ok(model) => Ok(model),
            Err(err) => {
                if is_unique_violation(&err) {
                    Err(DomainError::Conflict(format!(
                        "category '{}' already exists",
                        new.name
                    )))
                } else {
                    Err(DomainError::Db(err))
                }
            }
        }
    }

    async fn delete(&self, id: i32) -> Result<(), DomainError> {
        let row = category::Entity::find_by_id(id)
            .one(self.db.as_ref())
            .await?;
        let existing =
            row.ok_or_else(|| DomainError::NotFound(format!("category {id} not found")))?;
        existing.delete(self.db.as_ref()).await?;
        Ok(())
    }
}
