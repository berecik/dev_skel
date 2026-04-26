//! `/api/catalog` and `/api/orders` — order workflow endpoints.
//!
//! The catalog is a public browse surface (no auth required for GET).
//! Orders are per-user and follow a status lifecycle:
//! `draft` → `submitted` → `approved` / `rejected`.
//!
//! Every `/api/orders` endpoint requires a Bearer JWT — anonymous
//! requests get 401 from the `AuthUser` extractor.

use actix_web::{delete, get, post, put, web, HttpResponse};
use serde::{Deserialize, Serialize};
use sqlx::sqlite::SqlitePool;

use crate::auth::AuthUser;
use crate::error::ApiError;

// ---------------------------------------------------------------------------
// Serde structs — request payloads
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct CatalogItemPayload {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    pub price: f64,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default = "default_available")]
    pub available: bool,
}

fn default_available() -> bool {
    true
}

#[derive(Debug, Deserialize)]
pub struct AddLinePayload {
    pub catalog_item_id: i64,
    #[serde(default = "default_quantity")]
    pub quantity: i64,
}

fn default_quantity() -> i64 {
    1
}

#[derive(Debug, Deserialize)]
pub struct AddressPayload {
    pub street: String,
    pub city: String,
    pub zip_code: String,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ApprovePayload {
    #[serde(default)]
    pub wait_minutes: Option<i64>,
    #[serde(default)]
    pub feedback: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct RejectPayload {
    #[serde(default)]
    pub feedback: Option<String>,
}

// ---------------------------------------------------------------------------
// Serde structs — response shapes
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct CatalogItemRow {
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub price: f64,
    pub category: Option<String>,
    pub available: bool,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct OrderRow {
    pub id: i64,
    pub user_id: i64,
    pub status: Option<String>,
    pub created_at: Option<String>,
    pub submitted_at: Option<String>,
    pub wait_minutes: Option<i64>,
    pub feedback: Option<String>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct OrderLineRow {
    pub id: i64,
    pub order_id: i64,
    pub catalog_item_id: i64,
    pub quantity: i64,
    pub unit_price: f64,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct OrderAddressRow {
    pub id: i64,
    pub order_id: i64,
    pub street: String,
    pub city: String,
    pub zip_code: String,
    pub phone: Option<String>,
    pub notes: Option<String>,
}

/// Combined order response with nested lines and address.
#[derive(Debug, Serialize)]
pub struct OrderResponse {
    #[serde(flatten)]
    pub order: OrderRow,
}

/// Detailed order response including lines and address.
#[derive(Debug, Serialize)]
pub struct OrderDetailResponse {
    #[serde(flatten)]
    pub order: OrderRow,
    pub lines: Vec<OrderLineRow>,
    pub address: Option<OrderAddressRow>,
}

// ---------------------------------------------------------------------------
// Catalog endpoints (GET is public, POST/PUT/DELETE require auth)
// ---------------------------------------------------------------------------

/// `GET /api/catalog` — list all catalog items.
#[get("")]
pub async fn list_catalog(
    pool: web::Data<SqlitePool>,
) -> Result<HttpResponse, ApiError> {
    let rows = sqlx::query_as::<_, CatalogItemRow>(
        "SELECT id, name, description, price, category, available \
         FROM catalog_items ORDER BY name ASC",
    )
    .fetch_all(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(rows))
}

/// `POST /api/catalog` — create a catalog item (auth required).
#[post("")]
pub async fn create_catalog_item(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    payload: web::Json<CatalogItemPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation("catalog item name cannot be empty".to_string()));
    }
    if p.price < 0.0 {
        return Err(ApiError::Validation("price cannot be negative".to_string()));
    }
    let desc = p.description.unwrap_or_default();
    let cat = p.category.unwrap_or_default();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO catalog_items (name, description, price, category, available) \
         VALUES (?, ?, ?, ?, ?) RETURNING id",
    )
    .bind(&p.name)
    .bind(&desc)
    .bind(p.price)
    .bind(&cat)
    .bind(p.available)
    .fetch_one(pool.get_ref())
    .await?;
    let item = CatalogItemRow {
        id: row.0,
        name: p.name,
        description: if desc.is_empty() { None } else { Some(desc) },
        price: p.price,
        category: if cat.is_empty() { None } else { Some(cat) },
        available: p.available,
    };
    Ok(HttpResponse::Created().json(item))
}

/// `GET /api/catalog/{id}` — get a single catalog item.
#[get("/{id}")]
pub async fn get_catalog_item(
    pool: web::Data<SqlitePool>,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = sqlx::query_as::<_, CatalogItemRow>(
        "SELECT id, name, description, price, category, available \
         FROM catalog_items WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(pool.get_ref())
    .await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("catalog item {id} not found")))?;
    Ok(HttpResponse::Ok().json(item))
}

// ---------------------------------------------------------------------------
// Order endpoints (all require auth)
// ---------------------------------------------------------------------------

/// `POST /api/orders` — create a new draft order for the authenticated
/// user.
#[post("")]
pub async fn create_order(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO orders (user_id) VALUES (?) RETURNING id",
    )
    .bind(user.id)
    .fetch_one(pool.get_ref())
    .await?;
    let order = fetch_order(pool.get_ref(), row.0).await?;
    Ok(HttpResponse::Created().json(OrderResponse { order }))
}

/// `GET /api/orders` — list the authenticated user's orders.
#[get("")]
pub async fn list_orders(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = sqlx::query_as::<_, OrderRow>(
        "SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback \
         FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
    )
    .bind(user.id)
    .fetch_all(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(rows))
}

/// `GET /api/orders/{id}` — get order detail with lines + address.
#[get("/{id}")]
pub async fn get_order(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), id, user.id).await?;
    let lines = sqlx::query_as::<_, OrderLineRow>(
        "SELECT id, order_id, catalog_item_id, quantity, unit_price \
         FROM order_lines WHERE order_id = ? ORDER BY id ASC",
    )
    .bind(id)
    .fetch_all(pool.get_ref())
    .await?;
    let address = sqlx::query_as::<_, OrderAddressRow>(
        "SELECT id, order_id, street, city, zip_code, phone, notes \
         FROM order_addresses WHERE order_id = ?",
    )
    .bind(id)
    .fetch_optional(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(OrderDetailResponse { order, lines, address }))
}

/// `POST /api/orders/{id}/lines` — add a line item to a draft order.
#[post("/{id}/lines")]
pub async fn add_order_line(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<i64>,
    payload: web::Json<AddLinePayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), order_id, user.id).await?;
    if order.status.as_deref() != Some("draft") {
        return Err(ApiError::Validation("can only add lines to a draft order".to_string()));
    }
    let p = payload.into_inner();
    if p.quantity < 1 {
        return Err(ApiError::Validation("quantity must be at least 1".to_string()));
    }
    // Look up catalog item to get the unit price.
    let catalog_row = sqlx::query_as::<_, CatalogItemRow>(
        "SELECT id, name, description, price, category, available \
         FROM catalog_items WHERE id = ?",
    )
    .bind(p.catalog_item_id)
    .fetch_optional(pool.get_ref())
    .await?
    .ok_or_else(|| {
        ApiError::NotFound(format!("catalog item {} not found", p.catalog_item_id))
    })?;
    let line_row: (i64,) = sqlx::query_as(
        "INSERT INTO order_lines (order_id, catalog_item_id, quantity, unit_price) \
         VALUES (?, ?, ?, ?) RETURNING id",
    )
    .bind(order_id)
    .bind(p.catalog_item_id)
    .bind(p.quantity)
    .bind(catalog_row.price)
    .fetch_one(pool.get_ref())
    .await?;
    let line = OrderLineRow {
        id: line_row.0,
        order_id,
        catalog_item_id: p.catalog_item_id,
        quantity: p.quantity,
        unit_price: catalog_row.price,
    };
    Ok(HttpResponse::Created().json(line))
}

/// `DELETE /api/orders/{id}/lines/{line_id}` — remove a line from a
/// draft order.
#[delete("/{id}/lines/{line_id}")]
pub async fn remove_order_line(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<(i64, i64)>,
) -> Result<HttpResponse, ApiError> {
    let (order_id, line_id) = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), order_id, user.id).await?;
    if order.status.as_deref() != Some("draft") {
        return Err(ApiError::Validation("can only remove lines from a draft order".to_string()));
    }
    let res = sqlx::query("DELETE FROM order_lines WHERE id = ? AND order_id = ?")
        .bind(line_id)
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    if res.rows_affected() == 0 {
        return Err(ApiError::NotFound(format!("order line {line_id} not found")));
    }
    Ok(HttpResponse::NoContent().finish())
}

/// `PUT /api/orders/{id}/address` — set or update the delivery address
/// for an order.
#[put("/{id}/address")]
pub async fn set_order_address(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<i64>,
    payload: web::Json<AddressPayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), order_id, user.id).await?;
    if order.status.as_deref() != Some("draft") {
        return Err(ApiError::Validation("can only set address on a draft order".to_string()));
    }
    let p = payload.into_inner();
    if p.street.trim().is_empty() || p.city.trim().is_empty() || p.zip_code.trim().is_empty() {
        return Err(ApiError::Validation(
            "street, city, and zip_code are required".to_string(),
        ));
    }
    // Upsert via INSERT OR REPLACE (the UNIQUE constraint on order_id
    // makes this safe).
    sqlx::query(
        "INSERT INTO order_addresses (order_id, street, city, zip_code, phone, notes) \
         VALUES (?, ?, ?, ?, ?, ?) \
         ON CONFLICT(order_id) DO UPDATE SET \
         street = excluded.street, city = excluded.city, \
         zip_code = excluded.zip_code, phone = excluded.phone, \
         notes = excluded.notes",
    )
    .bind(order_id)
    .bind(&p.street)
    .bind(&p.city)
    .bind(&p.zip_code)
    .bind(&p.phone.unwrap_or_default())
    .bind(&p.notes.unwrap_or_default())
    .execute(pool.get_ref())
    .await?;
    let addr = sqlx::query_as::<_, OrderAddressRow>(
        "SELECT id, order_id, street, city, zip_code, phone, notes \
         FROM order_addresses WHERE order_id = ?",
    )
    .bind(order_id)
    .fetch_one(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(addr))
}

/// `POST /api/orders/{id}/submit` — submit a draft order.
#[post("/{id}/submit")]
pub async fn submit_order(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), order_id, user.id).await?;
    if order.status.as_deref() != Some("draft") {
        return Err(ApiError::Validation("only draft orders can be submitted".to_string()));
    }
    // Ensure the order has at least one line.
    let line_count: (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM order_lines WHERE order_id = ?")
            .bind(order_id)
            .fetch_one(pool.get_ref())
            .await?;
    if line_count.0 == 0 {
        return Err(ApiError::Validation(
            "cannot submit an order with no lines".to_string(),
        ));
    }
    sqlx::query(
        "UPDATE orders SET status = 'pending', submitted_at = datetime('now') WHERE id = ?",
    )
    .bind(order_id)
    .execute(pool.get_ref())
    .await?;
    let updated = fetch_order(pool.get_ref(), order_id).await?;
    Ok(HttpResponse::Ok().json(OrderResponse { order: updated }))
}

/// `POST /api/orders/{id}/approve` — approve a submitted order.
#[post("/{id}/approve")]
pub async fn approve_order(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
    payload: web::Json<ApprovePayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order(pool.get_ref(), order_id).await?;
    if order.status.as_deref() != Some("pending") {
        return Err(ApiError::Validation("only submitted orders can be approved".to_string()));
    }
    let p = payload.into_inner();
    sqlx::query("UPDATE orders SET status = 'approved', wait_minutes = ?, feedback = ? WHERE id = ?")
        .bind(p.wait_minutes)
        .bind(&p.feedback)
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    let updated = fetch_order(pool.get_ref(), order_id).await?;
    Ok(HttpResponse::Ok().json(OrderResponse { order: updated }))
}

/// `POST /api/orders/{id}/reject` — reject a submitted order.
#[post("/{id}/reject")]
pub async fn reject_order(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
    payload: web::Json<RejectPayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order(pool.get_ref(), order_id).await?;
    if order.status.as_deref() != Some("pending") {
        return Err(ApiError::Validation("only submitted orders can be rejected".to_string()));
    }
    let p = payload.into_inner();
    sqlx::query("UPDATE orders SET status = 'rejected', feedback = ? WHERE id = ?")
        .bind(&p.feedback)
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    let updated = fetch_order(pool.get_ref(), order_id).await?;
    Ok(HttpResponse::Ok().json(OrderResponse { order: updated }))
}

/// `DELETE /api/orders/{id}` — delete a draft order (cascading lines +
/// address).
#[delete("/{id}")]
pub async fn delete_order(
    pool: web::Data<SqlitePool>,
    user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(pool.get_ref(), order_id, user.id).await?;
    if order.status.as_deref() != Some("draft") {
        return Err(ApiError::Validation("only draft orders can be deleted".to_string()));
    }
    // Delete child rows first (SQLite FK cascade may not be on).
    sqlx::query("DELETE FROM order_lines WHERE order_id = ?")
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    sqlx::query("DELETE FROM order_addresses WHERE order_id = ?")
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    sqlx::query("DELETE FROM orders WHERE id = ?")
        .bind(order_id)
        .execute(pool.get_ref())
        .await?;
    Ok(HttpResponse::NoContent().finish())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Fetch a single order row by id. Returns 404 if not found.
async fn fetch_order(pool: &SqlitePool, id: i64) -> Result<OrderRow, ApiError> {
    sqlx::query_as::<_, OrderRow>(
        "SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback \
         FROM orders WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(pool)
    .await?
    .ok_or_else(|| ApiError::NotFound(format!("order {id} not found")))
}

/// Fetch a single order row ensuring it belongs to `user_id`. Returns
/// 404 if the order does not exist or belongs to another user.
async fn fetch_order_owned(
    pool: &SqlitePool,
    id: i64,
    user_id: i64,
) -> Result<OrderRow, ApiError> {
    let order = fetch_order(pool, id).await?;
    if order.user_id != user_id {
        return Err(ApiError::NotFound(format!("order {id} not found")));
    }
    Ok(order)
}
