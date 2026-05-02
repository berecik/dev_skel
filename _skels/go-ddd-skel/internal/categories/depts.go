// Dependency-injection providers for the categories resource.
package categories

import (
	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/categories/adapters"
)

// NewServiceFromDB wires a GORM adapter into a Service.
func NewServiceFromDB(db *gorm.DB) *Service {
	return NewService(adapters.NewGormCategoryRepository(db))
}
