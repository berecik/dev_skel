// Package items implements the /api/items resource — listing,
// fetching, creating, and completing items. Mirrors the FastAPI
// pilot's `app/example_items/` shape (models / adapters / service /
// routes) so the same DDD-light layout ports across stacks.
package items

import (
	"context"

	"github.com/example/go-ddd-skel/internal/models"
)

// Item is the canonical entity, re-exported from internal/models.
type Item = models.Item

// CreateItemDTO is the input shape for POST /api/items. Separate
// from the entity so request parsing has its own type to validate.
type CreateItemDTO struct {
	Name        string
	Description string
	IsCompleted bool
	CategoryID  *uint
}

// Repository is the storage abstraction every items.Service depends
// on. Concrete impls live under items/adapters.
type Repository interface {
	List(ctx context.Context) ([]Item, error)
	Get(ctx context.Context, id uint) (Item, error)
	Save(ctx context.Context, item *Item) error
	Delete(ctx context.Context, id uint) error
}
