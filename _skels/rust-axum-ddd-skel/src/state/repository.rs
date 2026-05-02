//! `StateRepository` — per-user JSON key/value store.

use async_trait::async_trait;

use crate::shared::DomainError;

#[async_trait]
pub trait StateRepository: Send + Sync {
    /// Return every `(key, value)` pair owned by `user_id`.
    async fn list_for_user(&self, user_id: i32) -> Result<Vec<(String, String)>, DomainError>;
    /// Insert or update the slice at `(user_id, key)`.
    async fn upsert(&self, user_id: i32, key: &str, value: String) -> Result<(), DomainError>;
    /// Remove the slice at `(user_id, key)`. No-op when missing.
    async fn delete(&self, user_id: i32, key: &str) -> Result<(), DomainError>;
}
