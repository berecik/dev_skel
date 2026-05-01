//! `/api/catalog` and `/api/orders` — order workflow endpoints.
//!
//! The catalog is a public browse surface (no auth required for GET).
//! Orders are per-user and follow a status lifecycle:
//! `draft` -> `pending` -> `approved` / `rejected`.
//!
//! Every `/api/orders` endpoint requires a Bearer JWT — anonymous
//! requests get 401 from the `AuthUser` extractor. SeaORM Active
//! Record drives every database access; there is no raw SQL in this
//! file.

use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use chrono::Utc;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, EntityTrait, ModelTrait,
    PaginatorTrait, QueryFilter, QueryOrder, Set,
};
use serde::Deserialize;
use serde_json::json;

use crate::auth::AuthUser;
use crate::entities::{catalog_item, order, order_address, order_line};
use crate::error::ApiError;
use crate::AppState;

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
    pub catalog_item_id: i32,
    #[serde(default = "default_quantity")]
    pub quantity: i32,
}

fn default_quantity() -> i32 {
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
    pub wait_minutes: Option<i32>,
    #[serde(default)]
    pub feedback: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct RejectPayload {
    #[serde(default)]
    pub feedback: Option<String>,
}

// ---------------------------------------------------------------------------
// Catalog endpoints (GET is public, POST requires auth)
// ---------------------------------------------------------------------------

/// `GET /api/catalog` — list all catalog items, ordered by name.
pub async fn list_catalog(
    State(state): State<Arc<AppState>>,
) -> Result<impl IntoResponse, ApiError> {
    let rows = catalog_item::Entity::find()
        .order_by_asc(catalog_item::Column::Name)
        .all(&state.db)
        .await?;
    Ok(Json(rows))
}

/// `POST /api/catalog` — create a catalog item (auth required).
pub async fn create_catalog_item(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Json(payload): Json<CatalogItemPayload>,
) -> Result<impl IntoResponse, ApiError> {
    if payload.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "catalog item name cannot be empty".to_string(),
        ));
    }
    if payload.price < 0.0 {
        return Err(ApiError::Validation("price cannot be negative".to_string()));
    }
    let new_item = catalog_item::ActiveModel {
        name: Set(payload.name),
        description: Set(payload.description.unwrap_or_default()),
        price: Set(payload.price),
        category: Set(payload.category.unwrap_or_default()),
        available: Set(payload.available),
        ..Default::default()
    };
    let inserted = new_item.insert(&state.db).await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

/// `GET /api/catalog/:id` — get a single catalog item.
pub async fn get_catalog_item(
    State(state): State<Arc<AppState>>,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let row = catalog_item::Entity::find_by_id(id).one(&state.db).await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("catalog item {id} not found")))?;
    Ok(Json(item))
}

// ---------------------------------------------------------------------------
// Order endpoints (all require auth)
// ---------------------------------------------------------------------------

/// `POST /api/orders` — create a new draft order for the authenticated
/// user.
pub async fn create_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let now = Utc::now();
    let new_order = order::ActiveModel {
        user_id: Set(user.id),
        status: Set("draft".to_string()),
        created_at: Set(now),
        submitted_at: Set(None),
        wait_minutes: Set(None),
        feedback: Set(None),
        ..Default::default()
    };
    let inserted = new_order.insert(&state.db).await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

/// `GET /api/orders` — list the authenticated user's orders.
pub async fn list_orders(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
) -> Result<impl IntoResponse, ApiError> {
    let rows = order::Entity::find()
        .filter(order::Column::UserId.eq(user.id))
        .order_by_desc(order::Column::CreatedAt)
        .order_by_desc(order::Column::Id)
        .all(&state.db)
        .await?;
    Ok(Json(rows))
}

/// `GET /api/orders/:id` — get order detail with lines + address
/// embedded under `lines` and `address` keys.
pub async fn get_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, id, user.id).await?;
    let lines = order_line::Entity::find()
        .filter(order_line::Column::OrderId.eq(id))
        .order_by_asc(order_line::Column::Id)
        .all(&state.db)
        .await?;
    let address = order_address::Entity::find()
        .filter(order_address::Column::OrderId.eq(id))
        .one(&state.db)
        .await?;
    Ok(Json(json!({
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "created_at": order.created_at,
        "submitted_at": order.submitted_at,
        "wait_minutes": order.wait_minutes,
        "feedback": order.feedback,
        "lines": lines,
        "address": address,
    })))
}

/// `POST /api/orders/:id/lines` — add a line item to a draft order.
/// The catalog item's current price is snapshotted onto the line as
/// `unit_price` so future catalog edits do not mutate historical
/// orders.
pub async fn add_order_line(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<AddLinePayload>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, order_id, user.id).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "can only add lines to a draft order".to_string(),
        ));
    }
    if payload.quantity < 1 {
        return Err(ApiError::Validation(
            "quantity must be at least 1".to_string(),
        ));
    }
    let catalog = catalog_item::Entity::find_by_id(payload.catalog_item_id)
        .one(&state.db)
        .await?
        .ok_or_else(|| {
            ApiError::NotFound(format!(
                "catalog item {} not found",
                payload.catalog_item_id
            ))
        })?;
    let new_line = order_line::ActiveModel {
        order_id: Set(order_id),
        catalog_item_id: Set(payload.catalog_item_id),
        quantity: Set(payload.quantity),
        unit_price: Set(catalog.price),
        ..Default::default()
    };
    let inserted = new_line.insert(&state.db).await?;
    Ok((StatusCode::CREATED, Json(inserted)))
}

/// `DELETE /api/orders/:id/lines/:line_id` — remove a line from a
/// draft order.
pub async fn remove_order_line(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path((order_id, line_id)): Path<(i32, i32)>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, order_id, user.id).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "can only remove lines from a draft order".to_string(),
        ));
    }
    let line = order_line::Entity::find()
        .filter(
            Condition::all()
                .add(order_line::Column::Id.eq(line_id))
                .add(order_line::Column::OrderId.eq(order_id)),
        )
        .one(&state.db)
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order line {line_id} not found")))?;
    line.delete(&state.db).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// `PUT /api/orders/:id/address` — set or update the delivery address
/// for a draft order. Implemented as a find-then-insert-or-update
/// flow (the underlying table has a UNIQUE constraint on `order_id`).
pub async fn set_order_address(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<AddressPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, order_id, user.id).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "can only set address on a draft order".to_string(),
        ));
    }
    if payload.street.trim().is_empty()
        || payload.city.trim().is_empty()
        || payload.zip_code.trim().is_empty()
    {
        return Err(ApiError::Validation(
            "street, city, and zip_code are required".to_string(),
        ));
    }
    let phone = payload.phone.unwrap_or_default();
    let notes = payload.notes.unwrap_or_default();

    let existing = order_address::Entity::find()
        .filter(order_address::Column::OrderId.eq(order_id))
        .one(&state.db)
        .await?;
    let saved = match existing {
        Some(found) => {
            let mut active: order_address::ActiveModel = found.into();
            active.street = Set(payload.street);
            active.city = Set(payload.city);
            active.zip_code = Set(payload.zip_code);
            active.phone = Set(phone);
            active.notes = Set(notes);
            active.update(&state.db).await?
        }
        None => {
            let new_addr = order_address::ActiveModel {
                order_id: Set(order_id),
                street: Set(payload.street),
                city: Set(payload.city),
                zip_code: Set(payload.zip_code),
                phone: Set(phone),
                notes: Set(notes),
                ..Default::default()
            };
            new_addr.insert(&state.db).await?
        }
    };
    Ok(Json(saved))
}

/// `POST /api/orders/:id/submit` — submit a draft order. Requires at
/// least one line; sets `status='pending'` and stamps `submitted_at`.
pub async fn submit_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, order_id, user.id).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "only draft orders can be submitted".to_string(),
        ));
    }
    let line_count = order_line::Entity::find()
        .filter(order_line::Column::OrderId.eq(order_id))
        .count(&state.db)
        .await?;
    if line_count == 0 {
        return Err(ApiError::Validation(
            "cannot submit an order with no lines".to_string(),
        ));
    }
    let mut active: order::ActiveModel = order.into();
    active.status = Set("pending".to_string());
    active.submitted_at = Set(Some(Utc::now()));
    let updated = active.update(&state.db).await?;
    Ok(Json(updated))
}

/// `POST /api/orders/:id/approve` — approve a pending order. Operator
/// endpoint: any authenticated user can approve any pending order
/// (the wrapper-shared backends agree on this contract; tighten via
/// role checks in production).
pub async fn approve_order(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<ApprovePayload>,
) -> Result<impl IntoResponse, ApiError> {
    let order = order::Entity::find_by_id(order_id)
        .one(&state.db)
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order {order_id} not found")))?;
    if order.status != "pending" {
        return Err(ApiError::Validation(
            "only submitted orders can be approved".to_string(),
        ));
    }
    let mut active: order::ActiveModel = order.into();
    active.status = Set("approved".to_string());
    active.wait_minutes = Set(payload.wait_minutes);
    active.feedback = Set(payload.feedback);
    let updated = active.update(&state.db).await?;
    Ok(Json(updated))
}

/// `POST /api/orders/:id/reject` — reject a pending order.
pub async fn reject_order(
    State(state): State<Arc<AppState>>,
    _user: AuthUser,
    Path(order_id): Path<i32>,
    Json(payload): Json<RejectPayload>,
) -> Result<impl IntoResponse, ApiError> {
    let order = order::Entity::find_by_id(order_id)
        .one(&state.db)
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order {order_id} not found")))?;
    if order.status != "pending" {
        return Err(ApiError::Validation(
            "only submitted orders can be rejected".to_string(),
        ));
    }
    let mut active: order::ActiveModel = order.into();
    active.status = Set("rejected".to_string());
    active.feedback = Set(payload.feedback);
    let updated = active.update(&state.db).await?;
    Ok(Json(updated))
}

/// `DELETE /api/orders/:id` — delete a draft order. The
/// `order_lines` and `order_addresses` rows are removed up-front so
/// the operation works whether or not SQLite FK cascade is enabled.
pub async fn delete_order(
    State(state): State<Arc<AppState>>,
    user: AuthUser,
    Path(order_id): Path<i32>,
) -> Result<impl IntoResponse, ApiError> {
    let order = fetch_order_owned(&state.db, order_id, user.id).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "only draft orders can be deleted".to_string(),
        ));
    }
    let _ = order_line::Entity::delete_many()
        .filter(order_line::Column::OrderId.eq(order_id))
        .exec(&state.db)
        .await?;
    let _ = order_address::Entity::delete_many()
        .filter(order_address::Column::OrderId.eq(order_id))
        .exec(&state.db)
        .await?;
    order.delete(&state.db).await?;
    Ok(StatusCode::NO_CONTENT)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Fetch a single order by id, ensuring it belongs to `user_id`.
/// Returns 404 (not 403) when the order does not exist OR belongs to
/// another user — the wrapper-shared contract is to never leak the
/// existence of another user's resource.
async fn fetch_order_owned(
    db: &DatabaseConnection,
    id: i32,
    user_id: i32,
) -> Result<order::Model, ApiError> {
    let row = order::Entity::find_by_id(id).one(db).await?;
    let order = row.ok_or_else(|| ApiError::NotFound(format!("order {id} not found")))?;
    if order.user_id != user_id {
        return Err(ApiError::NotFound(format!("order {id} not found")));
    }
    Ok(order)
}
