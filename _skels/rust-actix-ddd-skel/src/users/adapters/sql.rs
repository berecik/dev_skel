//! SeaORM-backed implementation of `UserRepository`.
//!
//! The only place in the skeleton that imports `DatabaseConnection`
//! together with `entities::user`. `auth` and `seed` reach for
//! `Arc<dyn UserRepository>` and never see SeaORM directly.

use std::sync::Arc;

use async_trait::async_trait;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QuerySelect, Set,
};

use crate::entities::user;
use crate::shared::{errors::is_unique_violation, DomainError};
use crate::users::repository::{NewUser, User, UserRepository};

/// SeaORM-backed `UserRepository`.
#[derive(Clone)]
pub struct SeaUserRepository {
    db: Arc<DatabaseConnection>,
}

impl SeaUserRepository {
    pub fn new(db: Arc<DatabaseConnection>) -> Self {
        Self { db }
    }
}

#[async_trait]
impl UserRepository for SeaUserRepository {
    async fn get(&self, id: i32) -> Result<User, DomainError> {
        let row = user::Entity::find_by_id(id).one(self.db.as_ref()).await?;
        row.ok_or_else(|| DomainError::NotFound(format!("user {id} not found")))
    }

    async fn get_by_username(&self, username: &str) -> Result<User, DomainError> {
        let row = user::Entity::find()
            .filter(user::Column::Username.eq(username))
            .one(self.db.as_ref())
            .await?;
        row.ok_or_else(|| DomainError::NotFound(format!("user '{username}' not found")))
    }

    async fn get_by_email(&self, email: &str) -> Result<User, DomainError> {
        let row = user::Entity::find()
            .filter(user::Column::Email.eq(email))
            .one(self.db.as_ref())
            .await?;
        row.ok_or_else(|| DomainError::NotFound(format!("email '{email}' not registered")))
    }

    async fn create(&self, new_user: NewUser) -> Result<User, DomainError> {
        let active = user::ActiveModel {
            username: Set(new_user.username.clone()),
            email: Set(new_user.email),
            password_hash: Set(new_user.password_hash),
            created_at: Set(new_user.created_at),
            ..Default::default()
        };
        match active.insert(self.db.as_ref()).await {
            Ok(model) => Ok(model),
            Err(err) => {
                if is_unique_violation(&err) {
                    Err(DomainError::Conflict(format!(
                        "user '{}' already exists",
                        new_user.username
                    )))
                } else {
                    Err(DomainError::Db(err))
                }
            }
        }
    }

    async fn principal(&self, id: i32) -> Result<(i32, String), DomainError> {
        let row = user::Entity::find_by_id(id)
            .select_only()
            .column(user::Column::Id)
            .column(user::Column::Username)
            .into_tuple::<(i32, String)>()
            .one(self.db.as_ref())
            .await?;
        row.ok_or_else(|| DomainError::NotFound(format!("user {id} not found")))
    }
}
