//! HTTP handlers for `/api/state`.

use std::collections::HashMap;
use std::sync::Arc;

use axum::{
    extract::{Path, State},
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::shared::ApiError;
use crate::state::service::StateService;

#[derive(Debug, Deserialize)]
pub struct UpsertPayload {
    pub value: String,
}

pub async fn list_state(
    State(svc): State<Arc<StateService>>,
    user: AuthUser,
) -> Result<Json<HashMap<String, String>>, ApiError> {
    let map = svc.map(user.id as i32).await?;
    Ok(Json(map))
}

pub async fn upsert_state(
    State(svc): State<Arc<StateService>>,
    user: AuthUser,
    Path(key): Path<String>,
    Json(body): Json<UpsertPayload>,
) -> Result<Json<serde_json::Value>, ApiError> {
    svc.upsert(user.id as i32, &key, body.value).await?;
    Ok(Json(serde_json::json!({ "key": key })))
}

pub async fn delete_state(
    State(svc): State<Arc<StateService>>,
    user: AuthUser,
    Path(key): Path<String>,
) -> Result<Json<serde_json::Value>, ApiError> {
    svc.delete(user.id as i32, &key).await?;
    Ok(Json(serde_json::json!({})))
}
