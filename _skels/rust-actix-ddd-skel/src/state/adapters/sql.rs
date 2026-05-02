//! SeaORM-backed implementation of `StateRepository`.

use std::sync::Arc;

use async_trait::async_trait;
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, QueryFilter,
    QuerySelect, Set,
};

use crate::entities::react_state;
use crate::shared::DomainError;
use crate::state::repository::StateRepository;

#[derive(Clone)]
pub struct SeaStateRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaStateRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl StateRepository for SeaStateRepository {
    async fn list_for_user(&self, user_id: i32) -> Result<Vec<(String, String)>, DomainError> {
        let rows = react_state::Entity::find()
            .filter(react_state::Column::UserId.eq(user_id))
            .select_only()
            .column(react_state::Column::Key)
            .column(react_state::Column::Value)
            .into_tuple::<(String, String)>()
            .all(self.db.as_ref())
            .await?;
        Ok(rows)
    }

    async fn upsert(&self, user_id: i32, key: &str, value: String) -> Result<(), DomainError> {
        let existing = react_state::Entity::find()
            .filter(
                Condition::all()
                    .add(react_state::Column::UserId.eq(user_id))
                    .add(react_state::Column::Key.eq(key)),
            )
            .one(self.db.as_ref())
            .await?;

        match existing {
            Some(row) => {
                let mut active: react_state::ActiveModel = row.into();
                active.value = Set(value);
                active.updated_at = Set(Utc::now());
                active.update(self.db.as_ref()).await?;
            }
            None => {
                let new_row = react_state::ActiveModel {
                    user_id: Set(user_id),
                    key: Set(key.to_string()),
                    value: Set(value),
                    updated_at: Set(Utc::now()),
                    ..Default::default()
                };
                new_row.insert(self.db.as_ref()).await?;
            }
        }
        Ok(())
    }

    async fn delete(&self, user_id: i32, key: &str) -> Result<(), DomainError> {
        let _ = react_state::Entity::delete_many()
            .filter(
                Condition::all()
                    .add(react_state::Column::UserId.eq(user_id))
                    .add(react_state::Column::Key.eq(key)),
            )
            .exec(self.db.as_ref())
            .await?;
        Ok(())
    }
}
