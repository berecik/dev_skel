// Service-layer logic for the /api/items resource.
package items

import (
	"context"
	"fmt"
	"strings"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Service coordinates items.Repository for HTTP routes. Exposed
// only via this layer so handlers stay free of *gorm.DB.
type Service struct {
	repo Repository
}

// NewService constructs an items Service.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

// List returns every item ordered by recency.
func (s *Service) List(ctx context.Context) ([]Item, error) {
	return s.repo.List(ctx)
}

// Get fetches a single item by id.
func (s *Service) Get(ctx context.Context, id uint) (Item, error) {
	return s.repo.Get(ctx, id)
}

// Create inserts a new item from the supplied DTO.
func (s *Service) Create(ctx context.Context, dto CreateItemDTO) (Item, error) {
	if strings.TrimSpace(dto.Name) == "" {
		return Item{}, fmt.Errorf("%w: item name cannot be empty", shared.ErrValidation)
	}
	item := Item{
		Name:        dto.Name,
		Description: dto.Description,
		IsCompleted: dto.IsCompleted,
		CategoryID:  dto.CategoryID,
	}
	if err := s.repo.Save(ctx, &item); err != nil {
		return Item{}, err
	}
	return item, nil
}

// Complete is the idempotent flip-to-done flow used by
// POST /api/items/{id}/complete.
func (s *Service) Complete(ctx context.Context, id uint) (Item, error) {
	item, err := s.repo.Get(ctx, id)
	if err != nil {
		return item, err
	}
	item.IsCompleted = true
	if err := s.repo.Save(ctx, &item); err != nil {
		return item, err
	}
	return item, nil
}
