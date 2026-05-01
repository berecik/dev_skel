use sea_orm::entity::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Serialize, Deserialize)]
#[sea_orm(table_name = "order_lines")]
pub struct Model {
    #[sea_orm(primary_key)]
    pub id: i32,
    pub order_id: i32,
    pub catalog_item_id: i32,
    #[sea_orm(default_value = 1)]
    pub quantity: i32,
    #[sea_orm(default_value = 0.0)]
    pub unit_price: f64,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(
        belongs_to = "super::order::Entity",
        from = "Column::OrderId",
        to = "super::order::Column::Id",
        on_delete = "Cascade"
    )]
    Order,
    #[sea_orm(
        belongs_to = "super::catalog_item::Entity",
        from = "Column::CatalogItemId",
        to = "super::catalog_item::Column::Id"
    )]
    CatalogItem,
}

impl Related<super::order::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Order.def()
    }
}

impl Related<super::catalog_item::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::CatalogItem.def()
    }
}

impl ActiveModelBehavior for ActiveModel {}
