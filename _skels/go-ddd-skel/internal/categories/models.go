// Package categories implements the /api/categories resource.
package categories

import (
	"context"

	"github.com/example/go-ddd-skel/internal/models"
)

// Category is the canonical entity (re-exported from internal/models).
type Category = models.Category

// CategoryDTO is the input shape for create/update.
type CategoryDTO struct {
	Name        string
	Description *string
}

// Repository is the storage abstraction every categories.Service
// depends on.
type Repository interface {
	List(ctx context.Context) ([]Category, error)
	Get(ctx context.Context, id uint) (Category, error)
	Save(ctx context.Context, c *Category) error
	Delete(ctx context.Context, c *Category) error
}
