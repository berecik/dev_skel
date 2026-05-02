// Service-layer logic for /api/orders. The service orchestrates
// the orders aggregate (Order + OrderLine + OrderAddress) and the
// cross-resource catalog lookup that snapshots the unit price into
// each line.
package orders

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Service is the entry point for the orders aggregate. Holds an
// orders.Repository plus a CatalogReader so cross-resource
// orchestration (line creation copies catalog price) is just a
// pure-Go method call.
type Service struct {
	orders  Repository
	catalog CatalogReader
}

// NewService builds an orders Service.
func NewService(repo Repository, cat CatalogReader) *Service {
	return &Service{orders: repo, catalog: cat}
}

// CreateOrder starts a fresh draft order owned by userID.
func (s *Service) CreateOrder(ctx context.Context, userID uint) (Order, error) {
	order := Order{UserID: userID, Status: "draft"}
	if err := s.orders.CreateOrder(ctx, &order); err != nil {
		return Order{}, err
	}
	return order, nil
}

// ListOrders returns every order owned by userID.
func (s *Service) ListOrders(ctx context.Context, userID uint) ([]Order, error) {
	return s.orders.ListOrdersForUser(ctx, userID)
}

// GetDetail fetches an order plus its lines + address. Returns
// shared.ErrNotFound when the order is missing or owned by someone
// else.
func (s *Service) GetDetail(ctx context.Context, orderID, userID uint) (Detail, error) {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return Detail{}, err
	}
	return s.buildDetail(ctx, order)
}

// AddLine appends a new line to a draft order, snapshotting the
// catalog item's current price.
func (s *Service) AddLine(ctx context.Context, orderID, userID uint, dto AddLineDTO) (OrderLine, error) {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return OrderLine{}, err
	}
	if order.Status != "draft" {
		return OrderLine{}, fmt.Errorf("%w: can only add lines to draft orders", shared.ErrValidation)
	}
	if dto.CatalogItemID == 0 {
		return OrderLine{}, fmt.Errorf("%w: catalog_item_id is required", shared.ErrValidation)
	}
	qty := dto.Quantity
	if qty < 1 {
		qty = 1
	}
	catItem, err := s.catalog.Get(ctx, dto.CatalogItemID)
	if err != nil {
		return OrderLine{}, err
	}
	line := OrderLine{
		OrderID:       orderID,
		CatalogItemID: dto.CatalogItemID,
		Quantity:      qty,
		UnitPrice:     catItem.Price,
	}
	if err := s.orders.CreateLine(ctx, &line); err != nil {
		return OrderLine{}, err
	}
	return line, nil
}

// DeleteLine removes a line from a draft order. Returns
// shared.ErrNotFound when the order or line does not exist (or is
// owned by someone else).
func (s *Service) DeleteLine(ctx context.Context, orderID, userID, lineID uint) error {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return err
	}
	if order.Status != "draft" {
		return fmt.Errorf("%w: can only remove lines from draft orders", shared.ErrValidation)
	}
	rows, err := s.orders.DeleteLine(ctx, orderID, lineID)
	if err != nil {
		return err
	}
	if rows == 0 {
		return fmt.Errorf("%w: order line %d", shared.ErrNotFound, lineID)
	}
	return nil
}

// UpsertAddress creates or replaces the delivery address for an
// order owned by userID.
func (s *Service) UpsertAddress(ctx context.Context, orderID, userID uint, dto AddressDTO) (OrderAddress, error) {
	if _, err := s.fetchUserOrder(ctx, orderID, userID); err != nil {
		return OrderAddress{}, err
	}
	addr, err := s.orders.GetAddressForOrder(ctx, orderID)
	switch {
	case err == nil:
		addr.Street = dto.Street
		addr.City = dto.City
		addr.ZipCode = dto.ZipCode
		addr.Phone = dto.Phone
		addr.Notes = dto.Notes
		if err := s.orders.SaveAddress(ctx, &addr); err != nil {
			return OrderAddress{}, err
		}
		return addr, nil
	case errors.Is(err, shared.ErrNotFound):
		addr = OrderAddress{
			OrderID: orderID,
			Street:  dto.Street,
			City:    dto.City,
			ZipCode: dto.ZipCode,
			Phone:   dto.Phone,
			Notes:   dto.Notes,
		}
		if err := s.orders.SaveAddress(ctx, &addr); err != nil {
			return OrderAddress{}, err
		}
		return addr, nil
	default:
		return OrderAddress{}, err
	}
}

// Submit transitions a draft order to pending. Requires at least
// one line.
func (s *Service) Submit(ctx context.Context, orderID, userID uint) (Detail, error) {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return Detail{}, err
	}
	if order.Status != "draft" {
		return Detail{}, fmt.Errorf("%w: only draft orders can be submitted", shared.ErrValidation)
	}
	lineCount, err := s.orders.CountLinesForOrder(ctx, orderID)
	if err != nil {
		return Detail{}, err
	}
	if lineCount == 0 {
		return Detail{}, fmt.Errorf("%w: cannot submit an order with no lines", shared.ErrValidation)
	}
	now := time.Now().UTC()
	order.Status = "pending"
	order.SubmittedAt = &now
	if err := s.orders.SaveOrder(ctx, &order); err != nil {
		return Detail{}, err
	}
	return s.buildDetail(ctx, order)
}

// Approve transitions a pending order to approved.
func (s *Service) Approve(ctx context.Context, orderID, userID uint, dto ApproveDTO) (Detail, error) {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return Detail{}, err
	}
	if order.Status != "pending" {
		return Detail{}, fmt.Errorf("%w: only submitted orders can be approved", shared.ErrValidation)
	}
	order.Status = "approved"
	order.WaitMinutes = dto.WaitMinutes
	order.Feedback = dto.Feedback
	if err := s.orders.SaveOrder(ctx, &order); err != nil {
		return Detail{}, err
	}
	return s.buildDetail(ctx, order)
}

// Reject transitions a pending order to rejected.
func (s *Service) Reject(ctx context.Context, orderID, userID uint, dto RejectDTO) (Detail, error) {
	order, err := s.fetchUserOrder(ctx, orderID, userID)
	if err != nil {
		return Detail{}, err
	}
	if order.Status != "pending" {
		return Detail{}, fmt.Errorf("%w: only submitted orders can be rejected", shared.ErrValidation)
	}
	order.Status = "rejected"
	order.Feedback = dto.Feedback
	if err := s.orders.SaveOrder(ctx, &order); err != nil {
		return Detail{}, err
	}
	return s.buildDetail(ctx, order)
}

// fetchUserOrder loads an order by id and verifies it belongs to
// the given user. Returns shared.ErrNotFound when not found OR not
// owned (so callers map both to 404, matching the prior contract).
func (s *Service) fetchUserOrder(ctx context.Context, orderID, userID uint) (Order, error) {
	o, err := s.orders.GetOrder(ctx, orderID)
	if err != nil {
		return o, err
	}
	if o.UserID != userID {
		return o, fmt.Errorf("%w: order %d not owned by user %d", shared.ErrNotFound, orderID, userID)
	}
	return o, nil
}

// buildDetail composes lines + address around an Order to produce
// the response shape every Detail-returning endpoint shares.
func (s *Service) buildDetail(ctx context.Context, order Order) (Detail, error) {
	lines, err := s.orders.ListLinesForOrder(ctx, order.ID)
	if err != nil {
		return Detail{}, err
	}
	if lines == nil {
		lines = []OrderLine{}
	}
	var address *OrderAddress
	addr, addrErr := s.orders.GetAddressForOrder(ctx, order.ID)
	switch {
	case addrErr == nil:
		address = &addr
	case errors.Is(addrErr, shared.ErrNotFound):
		address = nil
	default:
		return Detail{}, addrErr
	}
	return Detail{Order: order, Lines: lines, Address: address}, nil
}
