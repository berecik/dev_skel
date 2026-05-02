//! Database connection + schema bootstrap via SeaORM.
//!
//! The wrapper-shared `_shared/db.sqlite3` file is the canonical
//! storage location (resolved via `Config::database_url`); SeaORM
//! auto-detects the dialect from the URL scheme so swapping in
//! Postgres requires only changing `DATABASE_URL` — no code change.
//!
//! On first connect we issue idempotent `CREATE TABLE IF NOT EXISTS`
//! statements derived directly from the entity definitions in
//! `crate::entities`. This keeps the skel self-bootstrapping (no
//! separate migration step required) while still going through a
//! generic ORM rather than hand-written SQL.

use sea_orm::sea_query::table::TableCreateStatement;
use sea_orm::{ConnectionTrait, Database, DatabaseConnection, DbErr, Schema};

use crate::entities;

/// Connect to `database_url` and run idempotent table creation.
pub async fn connect_and_init(database_url: &str) -> Result<DatabaseConnection, DbErr> {
    let db = Database::connect(database_url).await?;

    // SQLite has FK enforcement off by default; turn it on so the
    // entity-declared `on_delete = SetNull` / `Cascade` constraints
    // actually fire. The pragma is a no-op for the Postgres dialect
    // (we test the dialect string before issuing it).
    if matches!(db.get_database_backend(), sea_orm::DatabaseBackend::Sqlite) {
        db.execute_unprepared("PRAGMA foreign_keys = ON;").await?;
    }

    let schema = Schema::new(db.get_database_backend());
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::User)).await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::Category)).await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::Item)).await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::ReactState))
        .await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::CatalogItem))
        .await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::Order)).await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::OrderLine))
        .await?;
    create_table_if_not_exists(&db, schema.create_table_from_entity(entities::OrderAddress))
        .await?;

    Ok(db)
}

async fn create_table_if_not_exists(
    db: &DatabaseConnection,
    mut stmt: TableCreateStatement,
) -> Result<(), DbErr> {
    stmt.if_not_exists();
    let backend = db.get_database_backend();
    db.execute(backend.build(&stmt)).await?;
    Ok(())
}
