//! Abstract `Repository` and `AbstractUnitOfWork` traits.
//!
//! These mirror the FastAPI pilot's `core.repository` / `core.uow`
//! and the Go skeleton's `shared.Repository[T]` / `shared.UnitOfWork`.
//!
//! Per-resource modules typically declare their own narrower
//! repository trait (`items::ItemRepository`,
//! `categories::CategoryRepository`, …) instead of using this generic
//! verbatim — it's documented here as a convention rather than
//! enforced. Resources that need transactional cross-aggregate writes
//! (orders today) declare a per-resource `XxxUnitOfWork` trait whose
//! shape mirrors `AbstractUnitOfWork` below.

use async_trait::async_trait;

use super::errors::DomainError;

/// Minimal CRUD surface shared across resources. `T` is the domain
/// entity (e.g. `entity::item::Model`), `Id` is its primary key.
///
/// Concrete adapters (e.g. `items::adapters::sql::SeaItemRepository`)
/// can implement this when their CRUD shape matches; resources with
/// richer needs declare their own resource-specific trait that
/// extends this one or replaces it entirely.
#[allow(dead_code)]
#[async_trait]
pub trait Repository<T, Id>: Send + Sync
where
    T: Send + Sync,
    Id: Send + Sync,
{
    async fn list(&self) -> Result<Vec<T>, DomainError>;
    async fn get(&self, id: Id) -> Result<T, DomainError>;
    async fn save(&self, entity: &T) -> Result<T, DomainError>;
    async fn delete(&self, id: Id) -> Result<(), DomainError>;
}

/// Transactional scope for cross-repository writes. Mirrors the
/// FastAPI pilot's `AbstractUnitOfWork`. Concrete UoWs (today only
/// the orders aggregate uses one) should expose typed per-repository
/// accessors so services don't downcast.
///
/// The Rust skeleton currently keeps every transaction inside a
/// single service method (orders is the most complex case and still
/// fits inside one SeaORM transaction), so this trait is declared
/// for symmetry with go-skel and FastAPI but no resource forces
/// callers through it yet.
#[allow(dead_code)]
#[async_trait]
pub trait AbstractUnitOfWork: Send + Sync {
    async fn commit(&mut self) -> Result<(), DomainError>;
    async fn rollback(&mut self) -> Result<(), DomainError>;
}
