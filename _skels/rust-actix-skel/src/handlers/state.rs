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
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;

use crate::auth::AuthUser;
use crate::error::ApiError;

#[derive(Debug, Deserialize)]
pub struct UpsertPayload {
    pub value: String,
}

#[get("")]
pub async fn list_state(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows: Vec<(String, String)> =
        sqlx::query_as("SELECT key, value FROM react_state WHERE user_id = ?")
            .bind(user.id)
            .fetch_all(pool.get_ref())
            .await?;
    let map: HashMap<String, String> = rows.into_iter().collect();
    Ok(HttpResponse::Ok().json(map))
}

#[put("/{key}")]
pub async fn upsert_state(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<String>,
    payload: web::Json<UpsertPayload>,
) -> Result<HttpResponse, ApiError> {
    let key = path.into_inner();
    let body = payload.into_inner();
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
    .execute(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(serde_json::json!({ "key": key })))
}

#[delete("/{key}")]
pub async fn delete_state(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<String>,
) -> Result<HttpResponse, ApiError> {
    let key = path.into_inner();
    sqlx::query("DELETE FROM react_state WHERE user_id = ? AND key = ?")
        .bind(user.id)
        .bind(&key)
        .execute(pool.get_ref())
        .await?;
    Ok(HttpResponse::Ok()
        .insert_header((header::CONTENT_TYPE, "application/json"))
        .body("{}"))
}
