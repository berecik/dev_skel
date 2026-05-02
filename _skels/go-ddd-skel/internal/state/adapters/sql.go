// Package adapters holds the GORM implementation of state.Repository.
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

// GormStateRepository is the default state.Repository.
type GormStateRepository struct {
	db *gorm.DB
}

// NewGormStateRepository returns a state.Repository over *gorm.DB.
func NewGormStateRepository(db *gorm.DB) *GormStateRepository {
	return &GormStateRepository{db: db}
}

func (r *GormStateRepository) ListForUser(ctx context.Context, userID uint) ([]models.ReactState, error) {
	var rows []models.ReactState
	if err := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("state_key").
		Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormStateRepository) GetForUser(ctx context.Context, userID uint, key string) (models.ReactState, error) {
	var row models.ReactState
	if err := r.db.WithContext(ctx).
		Where("user_id = ? AND state_key = ?", userID, key).
		First(&row).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return row, fmt.Errorf("%w: state key %q for user %d", shared.ErrNotFound, key, userID)
		}
		return row, err
	}
	return row, nil
}

func (r *GormStateRepository) Save(ctx context.Context, row *models.ReactState) error {
	return r.db.WithContext(ctx).Save(row).Error
}

func (r *GormStateRepository) DeleteForUser(ctx context.Context, userID uint, key string) error {
	res := r.db.WithContext(ctx).
		Where("user_id = ? AND state_key = ?", userID, key).
		Delete(&models.ReactState{})
	return res.Error
}
