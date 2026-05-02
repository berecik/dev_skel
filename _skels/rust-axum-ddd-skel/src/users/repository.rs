//! `UserRepository` — the storage abstraction `auth` and `seed`
//! depend on. Adapter implementations live under `users::adapters`.

use async_trait::async_trait;
use chrono::{DateTime, Utc};

use crate::shared::DomainError;

/// Minimal user record exposed through the repository. We re-use the
/// SeaORM model directly so callers see the same field set as a
/// `SELECT *` query — the repository abstraction protects them from
/// `DatabaseConnection`, not from the column layout.
pub use crate::entities::user::Model as User;

/// Input shape for `create`. Keeps the auth service free of
/// `ActiveModel` ergonomics.
#[derive(Debug, Clone)]
pub struct NewUser {
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub created_at: DateTime<Utc>,
}

#[async_trait]
pub trait UserRepository: Send + Sync {
    /// Fetch a user by primary key. Returns `DomainError::NotFound`
    /// when the row is absent.
    #[allow(dead_code)]
    async fn get(&self, id: i32) -> Result<User, DomainError>;

    /// Lookup by username. Returns `DomainError::NotFound` on miss.
    async fn get_by_username(&self, username: &str) -> Result<User, DomainError>;

    /// Lookup by email. Returns `DomainError::NotFound` on miss.
    async fn get_by_email(&self, email: &str) -> Result<User, DomainError>;

    /// Insert a fresh row. Returns the inserted `User` with the
    /// primary key populated. Translates UNIQUE failures to
    /// `DomainError::Conflict`.
    async fn create(&self, new_user: NewUser) -> Result<User, DomainError>;

    /// Project just `(id, username)` for cheap principal lookup
    /// inside the JWT extractor. Returns `DomainError::NotFound` on
    /// miss.
    async fn principal(&self, id: i32) -> Result<(i32, String), DomainError>;
}
