// Package adapters holds the GORM implementation of
// categories.Repository.
//
// Adapter packages deliberately do not import their parent resource
// package — that would create an import cycle since depts.go in the
// parent imports adapters. Go's structural typing lets the
// concrete type satisfy categories.Repository without naming it.
package adapters

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/models"
	"github.com/example/go-ddd-skel/internal/shared"
)

// GormCategoryRepository is the default categories.Repository.
type GormCategoryRepository struct {
	db *gorm.DB
}

// NewGormCategoryRepository returns a categories.Repository over a
// *gorm.DB.
func NewGormCategoryRepository(db *gorm.DB) *GormCategoryRepository {
	return &GormCategoryRepository{db: db}
}

func (r *GormCategoryRepository) List(ctx context.Context) ([]models.Category, error) {
	var rows []models.Category
	if err := r.db.WithContext(ctx).Order("id").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormCategoryRepository) Get(ctx context.Context, id uint) (models.Category, error) {
	var c models.Category
	if err := r.db.WithContext(ctx).First(&c, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return c, fmt.Errorf("%w: category %d", shared.ErrNotFound, id)
		}
		return c, err
	}
	return c, nil
}

func (r *GormCategoryRepository) Save(ctx context.Context, c *models.Category) error {
	if err := r.db.WithContext(ctx).Save(c).Error; err != nil {
		if shared.IsUniqueViolation(err) {
			return fmt.Errorf("%w: category with name '%s' already exists", shared.ErrConflict, c.Name)
		}
		return err
	}
	return nil
}

// Delete loads the row first so the Category.BeforeDelete hook
// (which nulls dependent items.category_id values) sees a fully-
// populated struct. Calling tx.Delete(&Category{}, id) runs the hook
// with only the FK as the WHERE clause and a zero-value receiver,
// so the hook's reference to c.ID would be wrong.
func (r *GormCategoryRepository) Delete(ctx context.Context, c *models.Category) error {
	return r.db.WithContext(ctx).Delete(c).Error
}
