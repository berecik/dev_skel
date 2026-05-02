//! SeaORM entities for the wrapper-shared backend stack.
//!
//! Every table the prior raw-SQL `db::init_schema` created has a
//! corresponding entity here. Handlers go through these models via
//! the SeaORM Active Record API (`Entity::find()`, `model.insert(db)`,
//! …) instead of writing raw SQL.

pub mod catalog_item;
pub mod category;
pub mod item;
pub mod order;
pub mod order_address;
pub mod order_line;
pub mod react_state;
pub mod user;

pub use catalog_item::Entity as CatalogItem;
pub use category::Entity as Category;
pub use item::Entity as Item;
pub use order::Entity as Order;
pub use order_address::Entity as OrderAddress;
pub use order_line::Entity as OrderLine;
pub use react_state::Entity as ReactState;
pub use user::Entity as User;
