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

use actix_web::{delete, get, http::header, put, web, HttpResponse};
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, QueryFilter,
    QuerySelect, Set,
};
use serde::Deserialize;

use crate::auth::AuthUser;
use crate::entities::react_state;
use crate::error::ApiError;

#[derive(Debug, Deserialize)]
pub struct UpsertPayload {
    pub value: String,
}

#[get("")]
pub async fn list_state(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = react_state::Entity::find()
        .filter(react_state::Column::UserId.eq(user.id as i32))
        .select_only()
        .column(react_state::Column::Key)
        .column(react_state::Column::Value)
        .into_tuple::<(String, String)>()
        .all(db.get_ref())
        .await?;
    let map: HashMap<String, String> = rows.into_iter().collect();
    Ok(HttpResponse::Ok().json(map))
}

#[put("/{key}")]
pub async fn upsert_state(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<String>,
    payload: web::Json<UpsertPayload>,
) -> Result<HttpResponse, ApiError> {
    let key = path.into_inner();
    let body = payload.into_inner();

    // SeaORM has no portable upsert helper across SQLite + Postgres
    // for composite uniques, so we branch on existence by
    // (user_id, key) and either UPDATE or INSERT. Matches the
    // pattern the Go skel uses for the same table.
    let existing = react_state::Entity::find()
        .filter(
            Condition::all()
                .add(react_state::Column::UserId.eq(user.id as i32))
                .add(react_state::Column::Key.eq(&key)),
        )
        .one(db.get_ref())
        .await?;

    if let Some(row) = existing {
        let mut active: react_state::ActiveModel = row.into();
        active.value = Set(body.value);
        active.updated_at = Set(Utc::now());
        active.update(db.get_ref()).await?;
    } else {
        let new_row = react_state::ActiveModel {
            user_id: Set(user.id as i32),
            key: Set(key.clone()),
            value: Set(body.value),
            updated_at: Set(Utc::now()),
            ..Default::default()
        };
        new_row.insert(db.get_ref()).await?;
    }
    Ok(HttpResponse::Ok().json(serde_json::json!({ "key": key })))
}

#[delete("/{key}")]
pub async fn delete_state(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<String>,
) -> Result<HttpResponse, ApiError> {
    let key = path.into_inner();
    react_state::Entity::delete_many()
        .filter(
            Condition::all()
                .add(react_state::Column::UserId.eq(user.id as i32))
                .add(react_state::Column::Key.eq(&key)),
        )
        .exec(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok()
        .insert_header((header::CONTENT_TYPE, "application/json"))
        .body("{}"))
}
