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
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, EntityTrait, QueryFilter, QuerySelect, Set,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::react_state;
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
    let rows = react_state::Entity::find()
        .filter(react_state::Column::UserId.eq(user.id))
        .select_only()
        .column(react_state::Column::Key)
        .column(react_state::Column::Value)
        .into_tuple::<(String, String)>()
        .all(&state.db)
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
    // SeaORM has no portable upsert helper across SQLite + Postgres
    // for composite uniques, so we branch on existence by
    // (user_id, key) and either UPDATE or INSERT. Matches the
    // pattern the actix skel uses for the same table.
    let existing = react_state::Entity::find()
        .filter(
            Condition::all()
                .add(react_state::Column::UserId.eq(user.id))
                .add(react_state::Column::Key.eq(&key)),
        )
        .one(&state.db)
        .await?;

    if let Some(row) = existing {
        let mut active: react_state::ActiveModel = row.into();
        active.value = Set(body.value);
        active.updated_at = Set(Utc::now());
        active.update(&state.db).await?;
    } else {
        let new_row = react_state::ActiveModel {
            user_id: Set(user.id),
            key: Set(key.clone()),
            value: Set(body.value),
            updated_at: Set(Utc::now()),
            ..Default::default()
        };
        new_row.insert(&state.db).await?;
    }
    Ok(Json(serde_json::json!({ "key": key })))
}

pub async fn delete_state(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(key): Path<String>,
) -> Result<Json<serde_json::Value>, ApiError> {
    react_state::Entity::delete_many()
        .filter(
            Condition::all()
                .add(react_state::Column::UserId.eq(user.id))
                .add(react_state::Column::Key.eq(&key)),
        )
        .exec(&state.db)
        .await?;
    Ok(Json(serde_json::json!({})))
}
