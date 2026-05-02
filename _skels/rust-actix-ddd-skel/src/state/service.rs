//! Service-layer logic for `/api/state`.

use std::collections::HashMap;
use std::sync::Arc;

use crate::shared::DomainError;
use crate::state::repository::StateRepository;

#[derive(Clone)]
pub struct StateService {
    repo: Arc<dyn StateRepository>,
}

impl StateService {
    pub fn new(repo: Arc<dyn StateRepository>) -> Self {
        Self { repo }
    }

    /// Return every key/value owned by `user_id` as a flat map.
    pub async fn map(&self, user_id: i32) -> Result<HashMap<String, String>, DomainError> {
        let rows = self.repo.list_for_user(user_id).await?;
        Ok(rows.into_iter().collect())
    }

    pub async fn upsert(
        &self,
        user_id: i32,
        key: &str,
        value: String,
    ) -> Result<(), DomainError> {
        if key.is_empty() {
            return Err(DomainError::Validation(
                "state key cannot be empty".to_string(),
            ));
        }
        self.repo.upsert(user_id, key, value).await
    }

    pub async fn delete(&self, user_id: i32, key: &str) -> Result<(), DomainError> {
        if key.is_empty() {
            return Err(DomainError::Validation(
                "state key cannot be empty".to_string(),
            ));
        }
        self.repo.delete(user_id, key).await
    }
}
