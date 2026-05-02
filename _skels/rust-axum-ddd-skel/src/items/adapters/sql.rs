//! SeaORM-backed implementation of `ItemRepository`.

use std::sync::Arc;

use async_trait::async_trait;
use chrono::Utc;
use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QueryOrder, Set,
};

use crate::entities::item;
use crate::items::repository::{Item, ItemRepository, NewItem};
use crate::shared::DomainError;

#[derive(Clone)]
pub struct SeaItemRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaItemRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl ItemRepository for SeaItemRepository {
    async fn list(&self) -> Result<Vec<Item>, DomainError> {
        let rows = item::Entity::find()
            .order_by_desc(item::Column::CreatedAt)
            .order_by_desc(item::Column::Id)
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn get(&self, id: i32) -> Result<Item, DomainError> {
        let row = item::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        row.ok_or_else(|| DomainError::NotFound(format!("item {id} not found")))
    }

    async fn create(&self, new: NewItem) -> Result<Item, DomainError> {
        let now = Utc::now();
        let active = item::ActiveModel {
            name: Set(new.name),
            description: Set(new.description),
            is_completed: Set(new.is_completed),
            category_id: Set(new.category_id),
            created_at: Set(now),
            updated_at: Set(now),
            ..Default::default()
        };
        let inserted = active.insert(self.db.as_ref()).await?;
        Ok(inserted)
    }

    async fn complete(&self, id: i32) -> Result<Item, DomainError> {
        let row = item::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        let existing =
            row.ok_or_else(|| DomainError::NotFound(format!("item {id} not found")))?;
        let mut active: item::ActiveModel = existing.into();
        active.is_completed = Set(true);
        active.updated_at = Set(Utc::now());
        let updated = active.update(self.db.as_ref()).await?;
        Ok(updated)
    }

    async fn clear_category(&self, category_id: i32) -> Result<(), DomainError> {
        item::Entity::update_many()
            .col_expr(item::Column::CategoryId, Expr::value(Option::<i32>::None))
            .col_expr(item::Column::UpdatedAt, Expr::value(Utc::now()))
            .filter(item::Column::CategoryId.eq(category_id))
            .exec(self.db.as_ref())
            .await?;
        Ok(())
    }
}
