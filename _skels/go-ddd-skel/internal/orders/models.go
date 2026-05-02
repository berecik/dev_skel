// Package orders implements the order workflow at /api/orders. The
// service is the most aggregate-shaped resource in the skeleton:
// every state-mutating operation works on an Order plus its
// dependent OrderLine + OrderAddress children, and creating a line
// reaches across to catalog.Repository to snapshot the unit price.
package orders

import (
	"context"

	"github.com/example/go-ddd-skel/internal/catalog"
	"github.com/example/go-ddd-skel/internal/models"
)

// Re-exports of the canonical entities so service callers stay
// decoupled from the GORM tags.
type (
	Order        = models.Order
	OrderLine    = models.OrderLine
	OrderAddress = models.OrderAddress
)

// Detail is the response shape for GET /api/orders/{id} and every
// mutating endpoint that returns a fully-loaded order.
type Detail struct {
	Order
	Lines   []OrderLine   `json:"lines"`
	Address *OrderAddress `json:"address"`
}

// AddLineDTO is the input shape for POST /api/orders/{id}/lines.
type AddLineDTO struct {
	CatalogItemID uint
	Quantity      int
}

// AddressDTO is the input shape for PUT /api/orders/{id}/address.
type AddressDTO struct {
	Street  string
	City    string
	ZipCode string
	Phone   *string
	Notes   *string
}

// ApproveDTO is the input shape for POST /api/orders/{id}/approve.
type ApproveDTO struct {
	WaitMinutes *int
	Feedback    *string
}

// RejectDTO is the input shape for POST /api/orders/{id}/reject.
type RejectDTO struct {
	Feedback *string
}

// Repository is the orders aggregate persistence abstraction. The
// service composes operations across orders, lines, and addresses
// via this single interface so all the GORM details live in one
// adapter.
type Repository interface {
	// Order operations.
	CreateOrder(ctx context.Context, order *Order) error
	GetOrder(ctx context.Context, id uint) (Order, error)
	ListOrdersForUser(ctx context.Context, userID uint) ([]Order, error)
	SaveOrder(ctx context.Context, order *Order) error

	// Line operations.
	CreateLine(ctx context.Context, line *OrderLine) error
	ListLinesForOrder(ctx context.Context, orderID uint) ([]OrderLine, error)
	CountLinesForOrder(ctx context.Context, orderID uint) (int64, error)
	DeleteLine(ctx context.Context, orderID, lineID uint) (int64, error)

	// Address operations.
	GetAddressForOrder(ctx context.Context, orderID uint) (OrderAddress, error)
	SaveAddress(ctx context.Context, addr *OrderAddress) error
}

// CatalogReader is the slim view onto catalog.Repository the orders
// service needs. Declared here so the orders package depends on the
// abstraction it actually uses, not the wider catalog API.
type CatalogReader interface {
	Get(ctx context.Context, id uint) (catalog.CatalogItem, error)
}
