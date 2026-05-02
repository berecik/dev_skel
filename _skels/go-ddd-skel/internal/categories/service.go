// Service-layer logic for /api/categories.
package categories

import (
	"context"
	"fmt"
	"strings"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Service coordinates categories.Repository for HTTP routes.
type Service struct {
	repo Repository
}

// NewService builds a categories Service.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

// List returns every category ordered by id.
func (s *Service) List(ctx context.Context) ([]Category, error) {
	return s.repo.List(ctx)
}

// Get fetches a category by id.
func (s *Service) Get(ctx context.Context, id uint) (Category, error) {
	return s.repo.Get(ctx, id)
}

// Create inserts a new category.
func (s *Service) Create(ctx context.Context, dto CategoryDTO) (Category, error) {
	if strings.TrimSpace(dto.Name) == "" {
		return Category{}, fmt.Errorf("%w: category name cannot be empty", shared.ErrValidation)
	}
	c := Category{Name: dto.Name}
	if dto.Description != nil {
		c.Description = *dto.Description
	}
	if err := s.repo.Save(ctx, &c); err != nil {
		return Category{}, err
	}
	return c, nil
}

// Update mutates an existing category by id.
func (s *Service) Update(ctx context.Context, id uint, dto CategoryDTO) (Category, error) {
	if strings.TrimSpace(dto.Name) == "" {
		return Category{}, fmt.Errorf("%w: category name cannot be empty", shared.ErrValidation)
	}
	c, err := s.repo.Get(ctx, id)
	if err != nil {
		return c, err
	}
	c.Name = dto.Name
	if dto.Description != nil {
		c.Description = *dto.Description
	} else {
		c.Description = ""
	}
	if err := s.repo.Save(ctx, &c); err != nil {
		return c, err
	}
	return c, nil
}

// Delete removes a category by id, running the cascade hook.
func (s *Service) Delete(ctx context.Context, id uint) error {
	c, err := s.repo.Get(ctx, id)
	if err != nil {
		return err
	}
	return s.repo.Delete(ctx, &c)
}
