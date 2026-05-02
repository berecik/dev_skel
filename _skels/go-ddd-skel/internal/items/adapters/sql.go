// Package adapters holds the GORM implementation of items.Repository.
//
// Adapter packages deliberately do not import their parent resource
// package — that would create an import cycle since depts.go in the
// parent imports adapters. Go's structural typing lets the
// concrete type satisfy items.Repository without naming it; we
// reference the entity via internal/models directly.
package adapters

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/models"
	"github.com/example/go-ddd-skel/internal/shared"
)

// GormItemRepository is the default items.Repository.
type GormItemRepository struct {
	db *gorm.DB
}

// NewGormItemRepository returns an items.Repository backed by GORM.
// Returns the concrete type so depts.go can wrap it in the
// interface; callers that store the value in an interface variable
// erase the type.
func NewGormItemRepository(db *gorm.DB) *GormItemRepository {
	return &GormItemRepository{db: db}
}

func (r *GormItemRepository) List(ctx context.Context) ([]models.Item, error) {
	var rows []models.Item
	if err := r.db.WithContext(ctx).
		Order("created_at DESC, id DESC").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormItemRepository) Get(ctx context.Context, id uint) (models.Item, error) {
	var item models.Item
	if err := r.db.WithContext(ctx).First(&item, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return item, fmt.Errorf("%w: item %d", shared.ErrNotFound, id)
		}
		return item, err
	}
	return item, nil
}

func (r *GormItemRepository) Save(ctx context.Context, item *models.Item) error {
	if err := r.db.WithContext(ctx).Save(item).Error; err != nil {
		if shared.IsUniqueViolation(err) {
			return fmt.Errorf("%w: %s", shared.ErrConflict, err.Error())
		}
		return err
	}
	return nil
}

func (r *GormItemRepository) Delete(ctx context.Context, id uint) error {
	res := r.db.WithContext(ctx).Delete(&models.Item{}, id)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("%w: item %d", shared.ErrNotFound, id)
	}
	return nil
}
