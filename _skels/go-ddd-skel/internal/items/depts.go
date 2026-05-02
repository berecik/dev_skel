// Dependency-injection providers for the items resource. Mirrors
// the FastAPI pilot's depts.py: each top-level provider returns a
// fully-wired collaborator main.go can hand to RegisterRoutes.
package items

import (
	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/items/adapters"
)

// NewServiceFromDB is the most common provider — wires a GORM
// adapter straight into a Service.
func NewServiceFromDB(db *gorm.DB) *Service {
	return NewService(adapters.NewGormItemRepository(db))
}
