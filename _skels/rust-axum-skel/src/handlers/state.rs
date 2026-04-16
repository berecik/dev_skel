//! `/api/state` — per-user JSON key/value store backing the React
//! `useAppState<T>(key, default)` hook.
//!
//! Wire format (from `ts-react-skel/src/state/state-api.ts`):
//! * `GET /api/state` → `{ "<key>": "<json string>" }` for the
//!   authenticated user.
//! * `PUT /api/state/<key>` body `{ "value": "<json string>" }` →
//!   upsert the slice. The backend stores the value verbatim — it
//!   never has to know the shape, which keeps the contract universal.
//! * `DELETE /api/state/<key>` → drop the slice.
//!
//! Every endpoint requires a Bearer JWT via the `AuthUser` extractor;
//! anonymous calls return 401.

use std::collections::HashMap;
use std::sync::Arc;

use axum::{
    extract::{Path, State},
    Json,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct UpsertPayload {
    pub value: String,
}

pub async fn list_state(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
) -> Result<Json<HashMap<String, String>>, ApiError> {
    let rows: Vec<(String, String)> =
        sqlx::query_as("SELECT key, value FROM react_state WHERE user_id = ?")
            .bind(user.id)
            .fetch_all(&state.pool)
            .await?;
    let map: HashMap<String, String> = rows.into_iter().collect();
    Ok(Json(map))
}

pub async fn upsert_state(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(key): Path<String>,
    Json(body): Json<UpsertPayload>,
) -> Result<Json<serde_json::Value>, ApiError> {
    sqlx::query(
        "INSERT INTO react_state (user_id, key, value, updated_at) \
         VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')) \
         ON CONFLICT(user_id, key) DO UPDATE SET \
             value = excluded.value, \
             updated_at = excluded.updated_at",
    )
    .bind(user.id)
    .bind(&key)
    .bind(&body.value)
    .execute(&state.pool)
    .await?;
    Ok(Json(serde_json::json!({ "key": key })))
}

pub async fn delete_state(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(key): Path<String>,
) -> Result<Json<serde_json::Value>, ApiError> {
    sqlx::query("DELETE FROM react_state WHERE user_id = ? AND key = ?")
        .bind(user.id)
        .bind(&key)
        .execute(&state.pool)
        .await?;
    Ok(Json(serde_json::json!({})))
}
