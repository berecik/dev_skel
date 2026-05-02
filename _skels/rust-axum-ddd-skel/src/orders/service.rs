//! Service-layer logic for `/api/orders`. Orchestrates the orders
//! aggregate (Order + OrderLine + OrderAddress) and the cross-
//! resource catalog lookup that snapshots the unit price into each
//! line.

use std::sync::Arc;

use chrono::Utc;
use serde::Serialize;

use crate::catalog::service::CatalogService;
use crate::orders::repository::{
    AddLine, NewAddress, Order, OrderAddress, OrderLine, OrderRepository, OrderStatusUpdate,
};
use crate::shared::DomainError;

#[derive(Debug, Clone)]
pub struct AddLineDTO {
    pub catalog_item_id: i32,
    pub quantity: i32,
}

#[derive(Debug, Clone)]
pub struct AddressDTO {
    pub street: String,
    pub city: String,
    pub zip_code: String,
    pub phone: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ApproveDTO {
    pub wait_minutes: Option<i32>,
    pub feedback: Option<String>,
}

#[derive(Debug, Clone)]
pub struct RejectDTO {
    pub feedback: Option<String>,
}

/// Response DTO for `/api/orders/:id` and every endpoint that
/// returns the fully-loaded order. The shape matches the prior
/// handler-monolith JSON byte-for-byte.
#[derive(Debug, Clone, Serialize)]
pub struct OrderDetail {
    pub id: i32,
    pub user_id: i32,
    pub status: String,
    pub created_at: chrono::DateTime<Utc>,
    pub submitted_at: Option<chrono::DateTime<Utc>>,
    pub wait_minutes: Option<i32>,
    pub feedback: Option<String>,
    pub lines: Vec<OrderLine>,
    pub address: Option<OrderAddress>,
}

impl OrderDetail {
    fn from_parts(order: Order, lines: Vec<OrderLine>, address: Option<OrderAddress>) -> Self {
        Self {
            id: order.id,
            user_id: order.user_id,
            status: order.status,
            created_at: order.created_at,
            submitted_at: order.submitted_at,
            wait_minutes: order.wait_minutes,
            feedback: order.feedback,
            lines,
            address,
        }
    }
}

#[derive(Clone)]
pub struct OrdersService {
    repo: Arc<dyn OrderRepository>,
    catalog: CatalogService,
}

impl OrdersService {
    pub fn new(repo: Arc<dyn OrderRepository>, catalog: CatalogService) -> Self {
        Self { repo, catalog }
    }

    pub async fn create_order(&self, user_id: i32) -> Result<Order, DomainError> {
        self.repo.create_order(user_id).await
    }

    pub async fn list_orders(&self, user_id: i32) -> Result<Vec<Order>, DomainError> {
        self.repo.list_orders_for_user(user_id).await
    }

    pub async fn get_detail(
        &self,
        order_id: i32,
        user_id: i32,
    ) -> Result<OrderDetail, DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        self.build_detail(order).await
    }

    pub async fn add_line(
        &self,
        order_id: i32,
        user_id: i32,
        dto: AddLineDTO,
    ) -> Result<OrderLine, DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        if order.status != "draft" {
            return Err(DomainError::Validation(
                "can only add lines to a draft order".to_string(),
            ));
        }
        if dto.quantity < 1 {
            return Err(DomainError::Validation(
                "quantity must be at least 1".to_string(),
            ));
        }
        let cat = self.catalog.get(dto.catalog_item_id).await?;
        self.repo
            .create_line(AddLine {
                order_id,
                catalog_item_id: dto.catalog_item_id,
                quantity: dto.quantity,
                unit_price: cat.price,
            })
            .await
    }

    pub async fn delete_line(
        &self,
        order_id: i32,
        user_id: i32,
        line_id: i32,
    ) -> Result<(), DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        if order.status != "draft" {
            return Err(DomainError::Validation(
                "can only remove lines from a draft order".to_string(),
            ));
        }
        let rows = self.repo.delete_line(order_id, line_id).await?;
        if rows == 0 {
            return Err(DomainError::NotFound(format!(
                "order line {line_id} not found"
            )));
        }
        Ok(())
    }

    pub async fn upsert_address(
        &self,
        order_id: i32,
        user_id: i32,
        dto: AddressDTO,
    ) -> Result<OrderAddress, DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        if order.status != "draft" {
            return Err(DomainError::Validation(
                "can only set address on a draft order".to_string(),
            ));
        }
        if dto.street.trim().is_empty()
            || dto.city.trim().is_empty()
            || dto.zip_code.trim().is_empty()
        {
            return Err(DomainError::Validation(
                "street, city, and zip_code are required".to_string(),
            ));
        }
        self.repo
            .upsert_address(
                order_id,
                NewAddress {
                    street: dto.street,
                    city: dto.city,
                    zip_code: dto.zip_code,
                    phone: dto.phone.unwrap_or_default(),
                    notes: dto.notes.unwrap_or_default(),
                },
            )
            .await
    }

    pub async fn submit(&self, order_id: i32, user_id: i32) -> Result<Order, DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        if order.status != "draft" {
            return Err(DomainError::Validation(
                "only draft orders can be submitted".to_string(),
            ));
        }
        let line_count = self.repo.count_lines_for_order(order_id).await?;
        if line_count == 0 {
            return Err(DomainError::Validation(
                "cannot submit an order with no lines".to_string(),
            ));
        }
        self.repo
            .apply_status_update(
                order_id,
                OrderStatusUpdate {
                    status: "pending".to_string(),
                    submitted_at: Some(Some(Utc::now())),
                    wait_minutes: None,
                    feedback: None,
                },
            )
            .await
    }

    pub async fn approve(&self, order_id: i32, dto: ApproveDTO) -> Result<Order, DomainError> {
        let order = self.repo.get_order(order_id).await?;
        if order.status != "pending" {
            return Err(DomainError::Validation(
                "only submitted orders can be approved".to_string(),
            ));
        }
        self.repo
            .apply_status_update(
                order_id,
                OrderStatusUpdate {
                    status: "approved".to_string(),
                    submitted_at: None,
                    wait_minutes: Some(dto.wait_minutes),
                    feedback: Some(dto.feedback),
                },
            )
            .await
    }

    pub async fn reject(&self, order_id: i32, dto: RejectDTO) -> Result<Order, DomainError> {
        let order = self.repo.get_order(order_id).await?;
        if order.status != "pending" {
            return Err(DomainError::Validation(
                "only submitted orders can be rejected".to_string(),
            ));
        }
        self.repo
            .apply_status_update(
                order_id,
                OrderStatusUpdate {
                    status: "rejected".to_string(),
                    submitted_at: None,
                    wait_minutes: None,
                    feedback: Some(dto.feedback),
                },
            )
            .await
    }

    pub async fn delete(&self, order_id: i32, user_id: i32) -> Result<(), DomainError> {
        let order = self.fetch_user_order(order_id, user_id).await?;
        if order.status != "draft" {
            return Err(DomainError::Validation(
                "only draft orders can be deleted".to_string(),
            ));
        }
        // Aggregate cleanup — explicit so the operation works whether
        // or not SQLite's FK cascade is enabled (and matches the
        // prior handler implementation byte-for-byte).
        self.repo.delete_lines_for_order(order_id).await?;
        self.repo.delete_addresses_for_order(order_id).await?;
        self.repo.delete_order(order_id).await
    }

    async fn fetch_user_order(
        &self,
        order_id: i32,
        user_id: i32,
    ) -> Result<Order, DomainError> {
        let order = self.repo.get_order(order_id).await?;
        if order.user_id != user_id {
            return Err(DomainError::NotFound(format!(
                "order {order_id} not found"
            )));
        }
        Ok(order)
    }

    async fn build_detail(&self, order: Order) -> Result<OrderDetail, DomainError> {
        let id = order.id;
        let lines = self.repo.list_lines_for_order(id).await?;
        let address = self.repo.get_address_for_order(id).await?;
        Ok(OrderDetail::from_parts(order, lines, address))
    }
}
