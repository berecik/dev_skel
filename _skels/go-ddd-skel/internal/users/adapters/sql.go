// Package adapters holds the GORM implementation of users.Repository.
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

// GormUserRepository is the default users.Repository.
type GormUserRepository struct {
	db *gorm.DB
}

// NewGormUserRepository returns a users.Repository over the given
// *gorm.DB. Use this from main.go's wiring.
func NewGormUserRepository(db *gorm.DB) *GormUserRepository {
	return &GormUserRepository{db: db}
}

func (r *GormUserRepository) List(ctx context.Context) ([]models.User, error) {
	var rows []models.User
	if err := r.db.WithContext(ctx).Order("id").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormUserRepository) Get(ctx context.Context, id uint) (models.User, error) {
	var u models.User
	if err := r.db.WithContext(ctx).First(&u, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return u, fmt.Errorf("%w: user %d", shared.ErrNotFound, id)
		}
		return u, err
	}
	return u, nil
}

func (r *GormUserRepository) GetByUsername(ctx context.Context, username string) (models.User, error) {
	var u models.User
	if err := r.db.WithContext(ctx).Where("username = ?", username).First(&u).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return u, fmt.Errorf("%w: user %q", shared.ErrNotFound, username)
		}
		return u, err
	}
	return u, nil
}

func (r *GormUserRepository) GetByEmail(ctx context.Context, email string) (models.User, error) {
	var u models.User
	if err := r.db.WithContext(ctx).Where("email = ?", email).First(&u).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return u, fmt.Errorf("%w: email %q", shared.ErrNotFound, email)
		}
		return u, err
	}
	return u, nil
}

func (r *GormUserRepository) Save(ctx context.Context, u *models.User) error {
	if err := r.db.WithContext(ctx).Save(u).Error; err != nil {
		if shared.IsUniqueViolation(err) {
			return fmt.Errorf("%w: %s", shared.ErrConflict, err.Error())
		}
		return err
	}
	return nil
}

func (r *GormUserRepository) Delete(ctx context.Context, id uint) error {
	res := r.db.WithContext(ctx).Delete(&models.User{}, id)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("%w: user %d", shared.ErrNotFound, id)
	}
	return nil
}
