// Package shared declares the repository / unit-of-work / domain-error
// abstractions every resource package builds on. The Repository
// generic mirrors the FastAPI pilot's `AbstractRepository` —
// services depend on this interface so concrete adapters (gorm,
// in-memory, mocks) can be swapped without touching service code.
package shared

import "context"

// Repository is the minimal CRUD surface every resource shares. T is
// the domain entity (e.g. models.Item). Resource packages typically
// extend this with their own filtering / search methods.
type Repository[T any] interface {
	List(ctx context.Context) ([]T, error)
	Get(ctx context.Context, id uint) (T, error)
	Save(ctx context.Context, entity *T) error
	Delete(ctx context.Context, id uint) error
}
