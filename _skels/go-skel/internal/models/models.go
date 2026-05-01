// Package models defines the GORM-managed entities for the
// wrapper-shared backend contract. Every column the prior raw-SQL
// schema declared maps to a struct field with the matching `json`
// tag so the HTTP layer's responses keep the wire format unchanged.
//
// `gorm.io/gorm`'s magic fields (`ID`, `CreatedAt`, `UpdatedAt`,
// `DeletedAt`) are reused where the existing schema names match;
// otherwise we override the column name explicitly.
package models

import (
	"time"

	"gorm.io/gorm"
)

// User mirrors the original `users` table.
type User struct {
	ID           uint      `gorm:"primaryKey;column:id" json:"id"`
	Username     string    `gorm:"size:255;not null;uniqueIndex;column:username" json:"username"`
	Email        string    `gorm:"size:255;not null;default:'';column:email" json:"email"`
	PasswordHash string    `gorm:"not null;column:password_hash" json:"-"`
	CreatedAt    time.Time `gorm:"autoCreateTime;column:created_at" json:"created_at"`
}

// Category mirrors the original `categories` table.
type Category struct {
	ID          uint      `gorm:"primaryKey;column:id" json:"id"`
	Name        string    `gorm:"size:255;not null;uniqueIndex;column:name" json:"name"`
	Description string    `gorm:"column:description" json:"description"`
	CreatedAt   time.Time `gorm:"autoCreateTime;column:created_at" json:"created_at"`
	UpdatedAt   time.Time `gorm:"autoUpdateTime;column:updated_at" json:"updated_at"`
}

// BeforeDelete enforces the original ON DELETE SET NULL semantics on
// `items.category_id` cross-dialect — GORM's AutoMigrate does not
// modify FK constraints on existing tables, so we apply the cascade
// explicitly via a hook. This keeps the contract identical to the
// raw-SQL schema the migration replaces.
func (c *Category) BeforeDelete(tx *gorm.DB) error {
	return tx.Model(&Item{}).
		Where("category_id = ?", c.ID).
		Update("category_id", nil).Error
}

// Item mirrors the original `items` table. Foreign key on category
// declared as `ON DELETE SET NULL` to match the prior raw schema.
type Item struct {
	ID          uint      `gorm:"primaryKey;column:id" json:"id"`
	Name        string    `gorm:"size:255;not null;column:name" json:"name"`
	Description string    `gorm:"column:description" json:"description"`
	IsCompleted bool      `gorm:"not null;default:false;column:is_completed" json:"is_completed"`
	CategoryID  *uint     `gorm:"column:category_id" json:"category_id"`
	CreatedAt   time.Time `gorm:"autoCreateTime;column:created_at" json:"created_at"`
	UpdatedAt   time.Time `gorm:"autoUpdateTime;column:updated_at" json:"updated_at"`
}

// ReactState is the per-user JSON-blob KV store keyed by
// `(user_id, state_key)`.
type ReactState struct {
	ID         uint      `gorm:"primaryKey;column:id" json:"id"`
	UserID     uint      `gorm:"not null;uniqueIndex:idx_react_state_user_key,priority:1;column:user_id" json:"user_id"`
	StateKey   string    `gorm:"size:255;not null;uniqueIndex:idx_react_state_user_key,priority:2;column:state_key" json:"state_key"`
	StateValue string    `gorm:"not null;column:state_value" json:"state_value"`
	UpdatedAt  time.Time `gorm:"autoUpdateTime;column:updated_at" json:"updated_at"`
}

// CatalogItem is a menu-position-style entry the orders flow
// references via `OrderLine.catalog_item_id`.
type CatalogItem struct {
	ID          uint      `gorm:"primaryKey;column:id" json:"id"`
	Name        string    `gorm:"size:255;not null;column:name" json:"name"`
	Description string    `gorm:"default:'';column:description" json:"description"`
	Price       float64   `gorm:"not null;default:0.0;column:price" json:"price"`
	Category    string    `gorm:"default:'';column:category" json:"category"`
	Available   bool      `gorm:"default:true;column:available" json:"available"`
	CreatedAt   time.Time `gorm:"autoCreateTime;column:created_at" json:"created_at"`
	UpdatedAt   time.Time `gorm:"autoUpdateTime;column:updated_at" json:"updated_at"`
}

// Order is the top-level order record.
type Order struct {
	ID          uint       `gorm:"primaryKey;column:id" json:"id"`
	UserID      uint       `gorm:"not null;column:user_id" json:"user_id"`
	Status      string     `gorm:"not null;default:'draft';column:status" json:"status"`
	CreatedAt   time.Time  `gorm:"autoCreateTime;column:created_at" json:"created_at"`
	SubmittedAt *time.Time `gorm:"column:submitted_at" json:"submitted_at"`
	WaitMinutes *int       `gorm:"column:wait_minutes" json:"wait_minutes"`
	Feedback    *string    `gorm:"column:feedback" json:"feedback"`
}

// OrderLine joins an Order to a CatalogItem with per-line quantity
// + unit price snapshot.
type OrderLine struct {
	ID            uint    `gorm:"primaryKey;column:id" json:"id"`
	OrderID       uint    `gorm:"not null;column:order_id" json:"order_id"`
	CatalogItemID uint    `gorm:"not null;column:catalog_item_id" json:"catalog_item_id"`
	Quantity      int     `gorm:"not null;default:1;column:quantity" json:"quantity"`
	UnitPrice     float64 `gorm:"not null;default:0;column:unit_price" json:"unit_price"`
}

// OrderAddress is a one-to-one delivery address per Order.
type OrderAddress struct {
	ID      uint    `gorm:"primaryKey;column:id" json:"id"`
	OrderID uint    `gorm:"not null;uniqueIndex;column:order_id" json:"order_id"`
	Street  string  `gorm:"not null;default:'';column:street" json:"street"`
	City    string  `gorm:"not null;default:'';column:city" json:"city"`
	ZipCode string  `gorm:"not null;default:'';column:zip_code" json:"zip_code"`
	Phone   *string `gorm:"column:phone" json:"phone"`
	Notes   *string `gorm:"column:notes" json:"notes"`
}

// All returns the slice of every entity for AutoMigrate.
func All() []any {
	return []any{
		&User{},
		&Category{},
		&Item{},
		&ReactState{},
		&CatalogItem{},
		&Order{},
		&OrderLine{},
		&OrderAddress{},
	}
}
