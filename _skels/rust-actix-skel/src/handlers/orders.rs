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

use actix_web::{delete, get, post, put, web, HttpResponse};
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
#[get("")]
pub async fn list_catalog(
    db: web::Data<DatabaseConnection>,
) -> Result<HttpResponse, ApiError> {
    let rows = catalog_item::Entity::find()
        .order_by_asc(catalog_item::Column::Name)
        .all(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok().json(rows))
}

/// `POST /api/catalog` — create a catalog item (auth required).
#[post("")]
pub async fn create_catalog_item(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    payload: web::Json<CatalogItemPayload>,
) -> Result<HttpResponse, ApiError> {
    let p = payload.into_inner();
    if p.name.trim().is_empty() {
        return Err(ApiError::Validation(
            "catalog item name cannot be empty".to_string(),
        ));
    }
    if p.price < 0.0 {
        return Err(ApiError::Validation("price cannot be negative".to_string()));
    }
    let new_item = catalog_item::ActiveModel {
        name: Set(p.name),
        description: Set(p.description.unwrap_or_default()),
        price: Set(p.price),
        category: Set(p.category.unwrap_or_default()),
        available: Set(p.available),
        ..Default::default()
    };
    let inserted = new_item.insert(db.get_ref()).await?;
    Ok(HttpResponse::Created().json(inserted))
}

/// `GET /api/catalog/{id}` — get a single catalog item.
#[get("/{id}")]
pub async fn get_catalog_item(
    db: web::Data<DatabaseConnection>,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let row = catalog_item::Entity::find_by_id(id)
        .one(db.get_ref())
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
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let now = Utc::now();
    let new_order = order::ActiveModel {
        user_id: Set(user.id as i32),
        status: Set("draft".to_string()),
        created_at: Set(now),
        submitted_at: Set(None),
        wait_minutes: Set(None),
        feedback: Set(None),
        ..Default::default()
    };
    let inserted = new_order.insert(db.get_ref()).await?;
    Ok(HttpResponse::Created().json(inserted))
}

/// `GET /api/orders` — list the authenticated user's orders.
#[get("")]
pub async fn list_orders(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
) -> Result<HttpResponse, ApiError> {
    let rows = order::Entity::find()
        .filter(order::Column::UserId.eq(user.id as i32))
        .order_by_desc(order::Column::CreatedAt)
        .order_by_desc(order::Column::Id)
        .all(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok().json(rows))
}

/// `GET /api/orders/{id}` — get order detail with lines + address
/// embedded under `lines` and `address` keys.
#[get("/{id}")]
pub async fn get_order(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let id = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), id, user.id as i32).await?;
    let lines = order_line::Entity::find()
        .filter(order_line::Column::OrderId.eq(id))
        .order_by_asc(order_line::Column::Id)
        .all(db.get_ref())
        .await?;
    let address = order_address::Entity::find()
        .filter(order_address::Column::OrderId.eq(id))
        .one(db.get_ref())
        .await?;
    Ok(HttpResponse::Ok().json(json!({
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

/// `POST /api/orders/{id}/lines` — add a line item to a draft order.
/// The catalog item's current price is snapshotted onto the line as
/// `unit_price` so future catalog edits do not mutate historical
/// orders.
#[post("/{id}/lines")]
pub async fn add_order_line(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<AddLinePayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), order_id, user.id as i32).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "can only add lines to a draft order".to_string(),
        ));
    }
    let p = payload.into_inner();
    if p.quantity < 1 {
        return Err(ApiError::Validation(
            "quantity must be at least 1".to_string(),
        ));
    }
    let catalog = catalog_item::Entity::find_by_id(p.catalog_item_id)
        .one(db.get_ref())
        .await?
        .ok_or_else(|| {
            ApiError::NotFound(format!("catalog item {} not found", p.catalog_item_id))
        })?;
    let new_line = order_line::ActiveModel {
        order_id: Set(order_id),
        catalog_item_id: Set(p.catalog_item_id),
        quantity: Set(p.quantity),
        unit_price: Set(catalog.price),
        ..Default::default()
    };
    let inserted = new_line.insert(db.get_ref()).await?;
    Ok(HttpResponse::Created().json(inserted))
}

/// `DELETE /api/orders/{id}/lines/{line_id}` — remove a line from a
/// draft order.
#[delete("/{id}/lines/{line_id}")]
pub async fn remove_order_line(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<(i32, i32)>,
) -> Result<HttpResponse, ApiError> {
    let (order_id, line_id) = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), order_id, user.id as i32).await?;
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
        .one(db.get_ref())
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order line {line_id} not found")))?;
    line.delete(db.get_ref()).await?;
    Ok(HttpResponse::NoContent().finish())
}

/// `PUT /api/orders/{id}/address` — set or update the delivery address
/// for a draft order. Implemented as a find-then-insert-or-update
/// flow (the underlying table has a UNIQUE constraint on `order_id`).
#[put("/{id}/address")]
pub async fn set_order_address(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<AddressPayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), order_id, user.id as i32).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "can only set address on a draft order".to_string(),
        ));
    }
    let p = payload.into_inner();
    if p.street.trim().is_empty() || p.city.trim().is_empty() || p.zip_code.trim().is_empty() {
        return Err(ApiError::Validation(
            "street, city, and zip_code are required".to_string(),
        ));
    }
    let phone = p.phone.unwrap_or_default();
    let notes = p.notes.unwrap_or_default();

    let existing = order_address::Entity::find()
        .filter(order_address::Column::OrderId.eq(order_id))
        .one(db.get_ref())
        .await?;
    let saved = match existing {
        Some(found) => {
            let mut active: order_address::ActiveModel = found.into();
            active.street = Set(p.street);
            active.city = Set(p.city);
            active.zip_code = Set(p.zip_code);
            active.phone = Set(phone);
            active.notes = Set(notes);
            active.update(db.get_ref()).await?
        }
        None => {
            let new_addr = order_address::ActiveModel {
                order_id: Set(order_id),
                street: Set(p.street),
                city: Set(p.city),
                zip_code: Set(p.zip_code),
                phone: Set(phone),
                notes: Set(notes),
                ..Default::default()
            };
            new_addr.insert(db.get_ref()).await?
        }
    };
    Ok(HttpResponse::Ok().json(saved))
}

/// `POST /api/orders/{id}/submit` — submit a draft order. Requires at
/// least one line; sets `status='pending'` and stamps `submitted_at`.
#[post("/{id}/submit")]
pub async fn submit_order(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), order_id, user.id as i32).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "only draft orders can be submitted".to_string(),
        ));
    }
    let line_count = order_line::Entity::find()
        .filter(order_line::Column::OrderId.eq(order_id))
        .count(db.get_ref())
        .await?;
    if line_count == 0 {
        return Err(ApiError::Validation(
            "cannot submit an order with no lines".to_string(),
        ));
    }
    let mut active: order::ActiveModel = order.into();
    active.status = Set("pending".to_string());
    active.submitted_at = Set(Some(Utc::now()));
    let updated = active.update(db.get_ref()).await?;
    Ok(HttpResponse::Ok().json(updated))
}

/// `POST /api/orders/{id}/approve` — approve a pending order. Operator
/// endpoint: any authenticated user can approve any pending order
/// (the wrapper-shared backends agree on this contract; tighten via
/// role checks in production).
#[post("/{id}/approve")]
pub async fn approve_order(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<ApprovePayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = order::Entity::find_by_id(order_id)
        .one(db.get_ref())
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order {order_id} not found")))?;
    if order.status != "pending" {
        return Err(ApiError::Validation(
            "only submitted orders can be approved".to_string(),
        ));
    }
    let p = payload.into_inner();
    let mut active: order::ActiveModel = order.into();
    active.status = Set("approved".to_string());
    active.wait_minutes = Set(p.wait_minutes);
    active.feedback = Set(p.feedback);
    let updated = active.update(db.get_ref()).await?;
    Ok(HttpResponse::Ok().json(updated))
}

/// `POST /api/orders/{id}/reject` — reject a pending order.
#[post("/{id}/reject")]
pub async fn reject_order(
    db: web::Data<DatabaseConnection>,
    _user: AuthUser,
    path: web::Path<i32>,
    payload: web::Json<RejectPayload>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = order::Entity::find_by_id(order_id)
        .one(db.get_ref())
        .await?
        .ok_or_else(|| ApiError::NotFound(format!("order {order_id} not found")))?;
    if order.status != "pending" {
        return Err(ApiError::Validation(
            "only submitted orders can be rejected".to_string(),
        ));
    }
    let p = payload.into_inner();
    let mut active: order::ActiveModel = order.into();
    active.status = Set("rejected".to_string());
    active.feedback = Set(p.feedback);
    let updated = active.update(db.get_ref()).await?;
    Ok(HttpResponse::Ok().json(updated))
}

/// `DELETE /api/orders/{id}` — delete a draft order. The
/// `order_lines` and `order_addresses` rows are removed up-front so
/// the operation works whether or not SQLite FK cascade is enabled.
#[delete("/{id}")]
pub async fn delete_order(
    db: web::Data<DatabaseConnection>,
    user: AuthUser,
    path: web::Path<i32>,
) -> Result<HttpResponse, ApiError> {
    let order_id = path.into_inner();
    let order = fetch_order_owned(db.get_ref(), order_id, user.id as i32).await?;
    if order.status != "draft" {
        return Err(ApiError::Validation(
            "only draft orders can be deleted".to_string(),
        ));
    }
    order_line::Entity::delete_many()
        .filter(order_line::Column::OrderId.eq(order_id))
        .exec(db.get_ref())
        .await?;
    order_address::Entity::delete_many()
        .filter(order_address::Column::OrderId.eq(order_id))
        .exec(db.get_ref())
        .await?;
    order.delete(db.get_ref()).await?;
    Ok(HttpResponse::NoContent().finish())
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
