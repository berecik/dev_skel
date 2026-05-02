// Service-layer logic for /api/catalog.
package catalog

import (
	"context"
	"fmt"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Service coordinates catalog.Repository for HTTP routes + the
// cross-resource orders flow (which holds a Repository directly).
type Service struct {
	repo Repository
}

// NewService builds a catalog Service.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

// List returns every catalog item.
func (s *Service) List(ctx context.Context) ([]CatalogItem, error) {
	return s.repo.List(ctx)
}

// Get fetches a catalog item by id.
func (s *Service) Get(ctx context.Context, id uint) (CatalogItem, error) {
	return s.repo.Get(ctx, id)
}

// Create inserts a new catalog item.
func (s *Service) Create(ctx context.Context, dto CreateCatalogItemDTO) (CatalogItem, error) {
	if dto.Name == "" {
		return CatalogItem{}, fmt.Errorf("%w: catalog item name cannot be empty", shared.ErrValidation)
	}
	item := CatalogItem{
		Name:      dto.Name,
		Price:     dto.Price,
		Available: true,
	}
	if dto.Description != nil {
		item.Description = *dto.Description
	}
	if dto.Category != nil {
		item.Category = *dto.Category
	}
	if dto.Available != nil {
		item.Available = *dto.Available
	}
	if err := s.repo.Save(ctx, &item); err != nil {
		return CatalogItem{}, err
	}
	return item, nil
}
