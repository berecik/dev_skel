// Package catalog implements the /api/catalog resource — menu /
// product positions referenced by the orders flow via
// OrderLine.catalog_item_id.
package catalog

import (
	"context"

	"github.com/example/go-ddd-skel/internal/models"
)

// CatalogItem is the canonical entity (re-exported from
// internal/models).
type CatalogItem = models.CatalogItem

// CreateCatalogItemDTO is the input shape for POST /api/catalog.
type CreateCatalogItemDTO struct {
	Name        string
	Description *string
	Price       float64
	Category    *string
	Available   *bool
}

// Repository is the storage abstraction every catalog.Service depends
// on. The orders package depends on a wider interface — see
// orders.CatalogReader — but the public catalog API only needs
// these methods.
type Repository interface {
	List(ctx context.Context) ([]CatalogItem, error)
	Get(ctx context.Context, id uint) (CatalogItem, error)
	Save(ctx context.Context, item *CatalogItem) error
}
