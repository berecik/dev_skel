//! SeaORM-backed implementation of `OrderRepository`.

use std::sync::Arc;

use async_trait::async_trait;
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, ModelTrait,
    PaginatorTrait, QueryFilter, QueryOrder, Set,
};

use crate::entities::{order, order_address, order_line};
use crate::orders::repository::{
    AddLine, NewAddress, Order, OrderAddress, OrderLine, OrderRepository, OrderStatusUpdate,
};
use crate::shared::DomainError;

#[derive(Clone)]
pub struct SeaOrderRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaOrderRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl OrderRepository for SeaOrderRepository {
    async fn create_order(&self, user_id: i32) -> Result<Order, DomainError> {
        let now = Utc::now();
        let active = order::ActiveModel {
            user_id: Set(user_id),
            status: Set("draft".to_string()),
            created_at: Set(now),
            submitted_at: Set(None),
            wait_minutes: Set(None),
            feedback: Set(None),
            ..Default::default()
        };
        let inserted = active.insert(self.db.as_ref()).await?;
        Ok(inserted)
    }

    async fn get_order(&self, id: i32) -> Result<Order, DomainError> {
        let row = order::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        row.ok_or_else(|| DomainError::NotFound(format!("order {id} not found")))
    }

    async fn list_orders_for_user(&self, user_id: i32) -> Result<Vec<Order>, DomainError> {
        let rows = order::Entity::find()
            .filter(order::Column::UserId.eq(user_id))
            .order_by_desc(order::Column::CreatedAt)
            .order_by_desc(order::Column::Id)
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn apply_status_update(
        &self,
        id: i32,
        update: OrderStatusUpdate,
    ) -> Result<Order, DomainError> {
        let row = order::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        let existing =
            row.ok_or_else(|| DomainError::NotFound(format!("order {id} not found")))?;
        let mut active: order::ActiveModel = existing.into();
        active.status = Set(update.status);
        if let Some(ts) = update.submitted_at {
            active.submitted_at = Set(ts);
        }
        if let Some(wait) = update.wait_minutes {
            active.wait_minutes = Set(wait);
        }
        if let Some(feedback) = update.feedback {
            active.feedback = Set(feedback);
        }
        let updated = active.update(self.db.as_ref()).await?;
        Ok(updated)
    }

    async fn delete_order(&self, id: i32) -> Result<(), DomainError> {
        let row = order::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        let existing =
            row.ok_or_else(|| DomainError::NotFound(format!("order {id} not found")))?;
        existing.delete(self.db.as_ref()).await?;
        Ok(())
    }

    async fn create_line(&self, payload: AddLine) -> Result<OrderLine, DomainError> {
        let active = order_line::ActiveModel {
            order_id: Set(payload.order_id),
            catalog_item_id: Set(payload.catalog_item_id),
            quantity: Set(payload.quantity),
            unit_price: Set(payload.unit_price),
            ..Default::default()
        };
        let inserted = active.insert(self.db.as_ref()).await?;
        Ok(inserted)
    }

    async fn list_lines_for_order(&self, order_id: i32) -> Result<Vec<OrderLine>, DomainError> {
        let rows = order_line::Entity::find()
            .filter(order_line::Column::OrderId.eq(order_id))
            .order_by_asc(order_line::Column::Id)
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn count_lines_for_order(&self, order_id: i32) -> Result<u64, DomainError> {
        let count = order_line::Entity::find()
            .filter(order_line::Column::OrderId.eq(order_id))
            .count(self.db.as_ref())
            .await?;
        Ok(count)
    }

    async fn delete_line(&self, order_id: i32, line_id: i32) -> Result<u64, DomainError> {
        let row = order_line::Entity::find()
            .filter(
                Condition::all()
                    .add(order_line::Column::Id.eq(line_id))
                    .add(order_line::Column::OrderId.eq(order_id)),
            )
            .one(self.db.as_ref())
            .await?;
        match row {
            Some(line) => {
                line.delete(self.db.as_ref()).await?;
                Ok(1)
            }
            None => Ok(0),
        }
    }

    async fn delete_lines_for_order(&self, order_id: i32) -> Result<(), DomainError> {
        let _ = order_line::Entity::delete_many()
            .filter(order_line::Column::OrderId.eq(order_id))
            .exec(self.db.as_ref())
            .await?;
        Ok(())
    }

    async fn get_address_for_order(
        &self,
        order_id: i32,
    ) -> Result<Option<OrderAddress>, DomainError> {
        let row = order_address::Entity::find()
            .filter(order_address::Column::OrderId.eq(order_id))
            .one(self.db.as_ref())
            .await?;
        Ok(row)
    }

    async fn upsert_address(
        &self,
        order_id: i32,
        payload: NewAddress,
    ) -> Result<OrderAddress, DomainError> {
        let existing = order_address::Entity::find()
            .filter(order_address::Column::OrderId.eq(order_id))
            .one(self.db.as_ref())
            .await?;
        let saved = match existing {
            Some(found) => {
                let mut active: order_address::ActiveModel = found.into();
                active.street = Set(payload.street);
                active.city = Set(payload.city);
                active.zip_code = Set(payload.zip_code);
                active.phone = Set(payload.phone);
                active.notes = Set(payload.notes);
                active.update(self.db.as_ref()).await?
            }
            None => {
                let new_addr = order_address::ActiveModel {
                    order_id: Set(order_id),
                    street: Set(payload.street),
                    city: Set(payload.city),
                    zip_code: Set(payload.zip_code),
                    phone: Set(payload.phone),
                    notes: Set(payload.notes),
                    ..Default::default()
                };
                new_addr.insert(self.db.as_ref()).await?
            }
        };
        Ok(saved)
    }

    async fn delete_addresses_for_order(&self, order_id: i32) -> Result<(), DomainError> {
        let _ = order_address::Entity::delete_many()
            .filter(order_address::Column::OrderId.eq(order_id))
            .exec(self.db.as_ref())
            .await?;
        Ok(())
    }
}
