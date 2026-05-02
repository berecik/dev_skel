// Package adapters holds the GORM implementation of
// catalog.Repository.
//
// Adapter packages deliberately do not import their parent resource
// package to avoid an import cycle with depts.go.
package adapters

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/models"
	"github.com/example/go-ddd-skel/internal/shared"
)

// GormCatalogRepository is the default catalog.Repository.
type GormCatalogRepository struct {
	db *gorm.DB
}

// NewGormCatalogRepository returns a catalog.Repository over *gorm.DB.
func NewGormCatalogRepository(db *gorm.DB) *GormCatalogRepository {
	return &GormCatalogRepository{db: db}
}

func (r *GormCatalogRepository) List(ctx context.Context) ([]models.CatalogItem, error) {
	var rows []models.CatalogItem
	if err := r.db.WithContext(ctx).Order("id").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormCatalogRepository) Get(ctx context.Context, id uint) (models.CatalogItem, error) {
	var item models.CatalogItem
	if err := r.db.WithContext(ctx).First(&item, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return item, fmt.Errorf("%w: catalog item %d", shared.ErrNotFound, id)
		}
		return item, err
	}
	return item, nil
}

func (r *GormCatalogRepository) Save(ctx context.Context, item *models.CatalogItem) error {
	return r.db.WithContext(ctx).Save(item).Error
}
