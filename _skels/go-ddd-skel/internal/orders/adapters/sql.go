// Package adapters holds the GORM implementation of orders.Repository.
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

// GormOrderRepository is the default orders.Repository.
type GormOrderRepository struct {
	db *gorm.DB
}

// NewGormOrderRepository returns an orders.Repository over *gorm.DB.
func NewGormOrderRepository(db *gorm.DB) *GormOrderRepository {
	return &GormOrderRepository{db: db}
}

// --- Order ----------------------------------------------------------------

func (r *GormOrderRepository) CreateOrder(ctx context.Context, order *models.Order) error {
	return r.db.WithContext(ctx).Create(order).Error
}

func (r *GormOrderRepository) GetOrder(ctx context.Context, id uint) (models.Order, error) {
	var o models.Order
	if err := r.db.WithContext(ctx).First(&o, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return o, fmt.Errorf("%w: order %d", shared.ErrNotFound, id)
		}
		return o, err
	}
	return o, nil
}

func (r *GormOrderRepository) ListOrdersForUser(ctx context.Context, userID uint) ([]models.Order, error) {
	var rows []models.Order
	if err := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("created_at DESC, id DESC").
		Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *GormOrderRepository) SaveOrder(ctx context.Context, order *models.Order) error {
	return r.db.WithContext(ctx).Save(order).Error
}

// --- Lines ----------------------------------------------------------------

func (r *GormOrderRepository) CreateLine(ctx context.Context, line *models.OrderLine) error {
	return r.db.WithContext(ctx).Create(line).Error
}

func (r *GormOrderRepository) ListLinesForOrder(ctx context.Context, orderID uint) ([]models.OrderLine, error) {
	var lines []models.OrderLine
	if err := r.db.WithContext(ctx).Where("order_id = ?", orderID).Find(&lines).Error; err != nil {
		return nil, err
	}
	return lines, nil
}

func (r *GormOrderRepository) CountLinesForOrder(ctx context.Context, orderID uint) (int64, error) {
	var n int64
	if err := r.db.WithContext(ctx).Model(&models.OrderLine{}).
		Where("order_id = ?", orderID).Count(&n).Error; err != nil {
		return 0, err
	}
	return n, nil
}

func (r *GormOrderRepository) DeleteLine(ctx context.Context, orderID, lineID uint) (int64, error) {
	res := r.db.WithContext(ctx).
		Where("id = ? AND order_id = ?", lineID, orderID).
		Delete(&models.OrderLine{})
	return res.RowsAffected, res.Error
}

// --- Address --------------------------------------------------------------

func (r *GormOrderRepository) GetAddressForOrder(ctx context.Context, orderID uint) (models.OrderAddress, error) {
	var addr models.OrderAddress
	if err := r.db.WithContext(ctx).Where("order_id = ?", orderID).First(&addr).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return addr, fmt.Errorf("%w: address for order %d", shared.ErrNotFound, orderID)
		}
		return addr, err
	}
	return addr, nil
}

func (r *GormOrderRepository) SaveAddress(ctx context.Context, addr *models.OrderAddress) error {
	return r.db.WithContext(ctx).Save(addr).Error
}
