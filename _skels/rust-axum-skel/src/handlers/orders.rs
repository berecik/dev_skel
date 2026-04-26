//! `/api/catalog` + `/api/orders` -- multi-entity order workflow.
//!
//! Demonstrates a domain with multiple related entities, status
//! transitions, nested detail responses, and cross-entity operations.
//! Mirrors the FastAPI skel's `orders.py` endpoint contract so every
//! dev_skel backend exposes the same order workflow API.
//!
//! Tables: `catalog_items`, `orders`, `order_lines`, `order_addresses`.
//! All order endpoints are user-scoped (JWT required via `AuthUser`).

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};

use crate::auth::AuthUser;
use crate::error::ApiError;
use crate::AppState;

// --------------------------------------------------------------------------- //
//  Row / response structs
// --------------------------------------------------------------------------- //

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct CatalogItemRow {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub price: f64,
    pub category: String,
    pub available: bool,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct OrderRow {
    pub id: i64,
    pub user_id: i64,
    pub status: String,
    pub created_at: String,
    pub submitted_at: Option<String>,
    pub wait_minutes: Option<i64>,
    pub feedback: Option<String>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct OrderLineRow {
    pub id: i64,
    pub catalog_item_id: i64,
    pub quantity: i64,
    pub unit_price: f64,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct AddressRow {
    pub id: i64,
    pub street: String,
    pub city: String,
    pub zip_code: String,
    pub phone: String,
    pub notes: String,
}

/// Nested detail response for `GET /api/orders/:id`.
#[derive(Debug, Serialize)]
pub struct OrderDetail {
    #[serde(flatten)]
    pub order: OrderRow,
    pub lines: Vec<OrderLineRow>,
    pub address: Option<AddressRow>,
}

// --------------------------------------------------------------------------- //
//  Request payloads
// --------------------------------------------------------------------------- //

#[derive(Debug, Deserialize)]
pub struct CreateCatalogItemPayload {
    pub name: String,
    pub price: f64,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_true")]
    pub available: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Deserialize)]
pub struct AddLinePayload {
    pub catalog_item_id: i64,
    #[serde(default = "default_one")]
    pub quantity: i64,
}

fn default_one() -> i64 {
    1
}

#[derive(Debug, Deserialize)]
pub struct AddressPayload {
    pub street: String,
    pub city: String,
    pub zip_code: String,
    #[serde(default)]
    pub phone: String,
    #[serde(default)]
    pub notes: String,
}

#[derive(Debug, Deserialize)]
pub struct ApprovePayload {
    pub wait_minutes: i64,
    pub feedback: String,
}

#[derive(Debug, Deserialize)]
pub struct RejectPayload {
    pub feedback: String,
}

// --------------------------------------------------------------------------- //
//  Catalog endpoints
// --------------------------------------------------------------------------- //

/// `GET /api/catalog` -- list all catalog items.
pub async fn list_catalog(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
) -> Result<Json<Vec<CatalogItemRow>>, ApiError> {
    let rows = sqlx::query_as::<_, CatalogItemRow>(
        "SELECT id, name, description, price, category, available \
         FROM catalog_items ORDER BY id ASC",
    )
    .fetch_all(&state.pool)
    .await?;
    Ok(Json(rows))
}

/// `GET /api/catalog/:id` -- single catalog item.
pub async fn get_catalog_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(item_id): Path<i64>,
) -> Result<Json<CatalogItemRow>, ApiError> {
    let row = sqlx::query_as::<_, CatalogItemRow>(
        "SELECT id, name, description, price, category, available \
         FROM catalog_items WHERE id = ?",
    )
    .bind(item_id)
    .fetch_optional(&state.pool)
    .await?;
    let item = row.ok_or_else(|| ApiError::NotFound("Catalog item not found".to_string()))?;
    Ok(Json(item))
}

/// `POST /api/catalog` -- create a new catalog item (auth required).
pub async fn create_catalog_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CreateCatalogItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "catalog item name cannot be empty".to_string(),
        ));
    }
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO catalog_items (name, description, price, category, available) \
         VALUES (?, ?, ?, ?, ?) RETURNING id",
    )
    .bind(&payload.name)
    .bind(&payload.description)
    .bind(payload.price)
    .bind(&payload.category)
    .bind(payload.available)
    .fetch_one(&state.pool)
    .await?;
    let item = CatalogItemRow {
        id: row.0,
        name: payload.name,
        description: payload.description,
        price: payload.price,
        category: payload.category,
        available: payload.available,
    };
    Ok((StatusCode::CREATED, Json(item)))
}

// --------------------------------------------------------------------------- //
//  Order CRUD
// --------------------------------------------------------------------------- //

/// `POST /api/orders` -- create a new draft order for the authenticated user.
pub async fn create_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let now = utc_iso8601();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO orders (user_id, status, created_at) VALUES (?, 'draft', ?) RETURNING id",
    )
    .bind(user.id)
    .bind(&now)
    .fetch_one(&state.pool)
    .await?;
    let order = OrderRow {
        id: row.0,
        user_id: user.id,
        status: "draft".to_string(),
        created_at: now,
        submitted_at: None,
        wait_minutes: None,
        feedback: None,
    };
    Ok((StatusCode::CREATED, Json(order)))
}

/// `GET /api/orders` -- list the authenticated user's orders.
pub async fn list_orders(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
) -> Result<Json<Vec<OrderRow>>, ApiError> {
    let rows = sqlx::query_as::<_, OrderRow>(
        "SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback \
         FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
    )
    .bind(user.id)
    .fetch_all(&state.pool)
    .await?;
    Ok(Json(rows))
}

/// `GET /api/orders/:id` -- order detail with nested lines + address.
pub async fn get_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i64>,
) -> Result<Json<OrderDetail>, ApiError> {
    let order = fetch_order(&state, order_id).await?;
    if order.user_id != user.id {
        return Err(ApiError::Forbidden("Not your order".to_string()));
    }
    let lines = sqlx::query_as::<_, OrderLineRow>(
        "SELECT id, catalog_item_id, quantity, unit_price \
         FROM order_lines WHERE order_id = ?",
    )
    .bind(order_id)
    .fetch_all(&state.pool)
    .await?;
    let address = sqlx::query_as::<_, AddressRow>(
        "SELECT id, street, city, zip_code, phone, notes \
         FROM order_addresses WHERE order_id = ?",
    )
    .bind(order_id)
    .fetch_optional(&state.pool)
    .await?;
    Ok(Json(OrderDetail {
        order,
        lines,
        address,
    }))
}

// --------------------------------------------------------------------------- //
//  Order lines
// --------------------------------------------------------------------------- //

/// `POST /api/orders/:order_id/lines` -- add a line to a draft order.
pub async fn add_line(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i64>,
    Json(payload): Json<AddLinePayload>,
) -> Result<impl IntoResponse, ApiError> {
    let _order = get_draft(&state, order_id, &user).await?;
    let cat = sqlx::query_as::<_, (f64,)>(
        "SELECT price FROM catalog_items WHERE id = ?",
    )
    .bind(payload.catalog_item_id)
    .fetch_optional(&state.pool)
    .await?
    .ok_or_else(|| ApiError::NotFound("Catalog item not found".to_string()))?;
    let unit_price = cat.0;
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO order_lines (order_id, catalog_item_id, quantity, unit_price) \
         VALUES (?, ?, ?, ?) RETURNING id",
    )
    .bind(order_id)
    .bind(payload.catalog_item_id)
    .bind(payload.quantity)
    .bind(unit_price)
    .fetch_one(&state.pool)
    .await?;
    let line = OrderLineRow {
        id: row.0,
        catalog_item_id: payload.catalog_item_id,
        quantity: payload.quantity,
        unit_price,
    };
    Ok((StatusCode::CREATED, Json(line)))
}

/// `DELETE /api/orders/:order_id/lines/:line_id` -- remove a line from
/// a draft order.
pub async fn remove_line(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path((order_id, line_id)): Path<(i64, i64)>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let _order = get_draft(&state, order_id, &user).await?;
    let res = sqlx::query(
        "DELETE FROM order_lines WHERE id = ? AND order_id = ?",
    )
    .bind(line_id)
    .bind(order_id)
    .execute(&state.pool)
    .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound("Line not found".to_string()));
    }
    Ok(Json(serde_json::json!({ "ok": true })))
}

// --------------------------------------------------------------------------- //
//  Order address
// --------------------------------------------------------------------------- //

/// `PUT /api/orders/:order_id/address` -- set or update the delivery
/// address on a draft order (upsert).
pub async fn set_address(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i64>,
    Json(payload): Json<AddressPayload>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let _order = get_draft(&state, order_id, &user).await?;
    let existing: Option<(i64,)> = sqlx::query_as(
        "SELECT id FROM order_addresses WHERE order_id = ?",
    )
    .bind(order_id)
    .fetch_optional(&state.pool)
    .await?;
    if let Some((addr_id,)) = existing {
        sqlx::query(
            "UPDATE order_addresses SET street = ?, city = ?, zip_code = ?, phone = ?, notes = ? \
             WHERE id = ?",
        )
        .bind(&payload.street)
        .bind(&payload.city)
        .bind(&payload.zip_code)
        .bind(&payload.phone)
        .bind(&payload.notes)
        .bind(addr_id)
        .execute(&state.pool)
        .await?;
    } else {
        sqlx::query(
            "INSERT INTO order_addresses (order_id, street, city, zip_code, phone, notes) \
             VALUES (?, ?, ?, ?, ?, ?)",
        )
        .bind(order_id)
        .bind(&payload.street)
        .bind(&payload.city)
        .bind(&payload.zip_code)
        .bind(&payload.phone)
        .bind(&payload.notes)
        .execute(&state.pool)
        .await?;
    }
    Ok(Json(serde_json::json!({ "ok": true })))
}

// --------------------------------------------------------------------------- //
//  Status transitions
// --------------------------------------------------------------------------- //

/// `POST /api/orders/:order_id/submit` -- move a draft order to
/// pending.
pub async fn submit_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i64>,
) -> Result<Json<OrderRow>, ApiError> {
    let _order = get_draft(&state, order_id, &user).await?;
    let now = utc_iso8601();
    sqlx::query("UPDATE orders SET status = 'pending', submitted_at = ? WHERE id = ?")
        .bind(&now)
        .bind(order_id)
        .execute(&state.pool)
        .await?;
    let order = fetch_order(&state, order_id).await?;
    Ok(Json(order))
}

/// `POST /api/orders/:order_id/approve` -- approve a pending order.
pub async fn approve_order(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(order_id): Path<i64>,
    Json(payload): Json<ApprovePayload>,
) -> Result<Json<OrderRow>, ApiError> {
    let _order = get_pending(&state, order_id).await?;
    sqlx::query(
        "UPDATE orders SET status = 'approved', wait_minutes = ?, feedback = ? WHERE id = ?",
    )
    .bind(payload.wait_minutes)
    .bind(&payload.feedback)
    .bind(order_id)
    .execute(&state.pool)
    .await?;
    let order = fetch_order(&state, order_id).await?;
    Ok(Json(order))
}

/// `POST /api/orders/:order_id/reject` -- reject a pending order.
pub async fn reject_order(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(order_id): Path<i64>,
    Json(payload): Json<RejectPayload>,
) -> Result<Json<OrderRow>, ApiError> {
    let _order = get_pending(&state, order_id).await?;
    sqlx::query("UPDATE orders SET status = 'rejected', feedback = ? WHERE id = ?")
        .bind(&payload.feedback)
        .bind(order_id)
        .execute(&state.pool)
        .await?;
    let order = fetch_order(&state, order_id).await?;
    Ok(Json(order))
}

// --------------------------------------------------------------------------- //
//  Helpers
// --------------------------------------------------------------------------- //

async fn fetch_order(state: &Arc<AppState>, order_id: i64) -> Result<OrderRow, ApiError> {
    sqlx::query_as::<_, OrderRow>(
        "SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback \
         FROM orders WHERE id = ?",
    )
    .bind(order_id)
    .fetch_optional(&state.pool)
    .await?
    .ok_or_else(|| ApiError::NotFound("Order not found".to_string()))
}

/// Fetch the order and verify it belongs to `user` and is in `draft`
/// status.
async fn get_draft(
    state: &Arc<AppState>,
    order_id: i64,
    user: &AuthUser,
) -> Result<OrderRow, ApiError> {
    let order = fetch_order(state, order_id).await?;
    if order.user_id != user.id {
        return Err(ApiError::Forbidden("Not your order".to_string()));
    }
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "Order must be in draft status".to_string(),
        ));
    }
    Ok(order)
}

/// Fetch the order and verify it is in `pending` status.
async fn get_pending(state: &Arc<AppState>, order_id: i64) -> Result<OrderRow, ApiError> {
    let order = fetch_order(state, order_id).await?;
    if order.status != "pending" {
        return Err(ApiError::Validation(
            "Order must be in pending status".to_string(),
        ));
    }
    Ok(order)
}

fn utc_iso8601() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string()
}
