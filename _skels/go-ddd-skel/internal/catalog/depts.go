// Dependency-injection providers for the catalog resource.
package catalog

import (
	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/catalog/adapters"
)

// NewRepositoryFromDB returns a Repository over *gorm.DB. Exported so
// the orders package can take a direct dependency on the catalog
// repo without going through the catalog Service.
func NewRepositoryFromDB(db *gorm.DB) Repository {
	return adapters.NewGormCatalogRepository(db)
}

// NewServiceFromDB wires a GORM adapter into a Service.
func NewServiceFromDB(db *gorm.DB) *Service {
	return NewService(NewRepositoryFromDB(db))
}
