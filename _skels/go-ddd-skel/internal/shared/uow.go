// UnitOfWork bundles a transactional scope across multiple
// repositories. Mirrors `AbstractUnitOfWork` in the FastAPI pilot —
// services that need cross-aggregate atomicity ask for one of these
// from a UoW factory and commit/rollback explicitly.
//
// The Go skeleton currently keeps every transaction inside a single
// service method (orders is the most complex case and still fits in
// a single GORM transaction), so the interface is declared but no
// resource forces callers through it yet. Concrete adapters can
// implement this when the time comes without churning the service
// layer.
package shared

import "context"

// UnitOfWork is a transactional scope. Begin returns a fresh UoW
// bound to ctx; Commit / Rollback close it. Implementations also
// expose typed repository accessors via type assertion or via
// resource-specific sub-interfaces.
type UnitOfWork interface {
	Begin(ctx context.Context) (UnitOfWork, error)
	Commit() error
	Rollback() error
}
