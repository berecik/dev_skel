// Dependency-injection providers for the state resource.
package state

import (
	"gorm.io/gorm"

	"github.com/example/go-ddd-skel/internal/state/adapters"
)

// NewServiceFromDB wires a GORM adapter into a Service.
func NewServiceFromDB(db *gorm.DB) *Service {
	return NewService(adapters.NewGormStateRepository(db))
}
