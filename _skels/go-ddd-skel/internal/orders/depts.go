// Dependency-injection providers for the orders resource.
package orders

import (
	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/catalog"
	"github.com/example/go-ddd-skel/internal/orders/adapters"
)

// NewServiceFromDB wires GORM adapters for both orders and catalog
// into a single orders Service. catalog.Repository satisfies
// CatalogReader directly because it exposes Get(ctx, id).
func NewServiceFromDB(db *gorm.DB) *Service {
	return NewService(
		adapters.NewGormOrderRepository(db),
		catalog.NewRepositoryFromDB(db),
	)
}
