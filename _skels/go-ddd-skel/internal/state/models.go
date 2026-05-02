// Package state implements the per-user JSON KV store at /api/state.
// Slightly different shape from the standard CRUD resources — keys
// are scoped to the authenticated user and the public response is a
// flat key→value map rather than a list of records.
package state

import (
	"context"

	"github.com/example/go-ddd-skel/internal/models"
)

// ReactState is the canonical entity (re-exported from
// internal/models).
type ReactState = models.ReactState

// Repository is the storage abstraction every state.Service depends
// on. Methods are user-scoped because the wire-level resource is
// per-user.
type Repository interface {
	ListForUser(ctx context.Context, userID uint) ([]ReactState, error)
	GetForUser(ctx context.Context, userID uint, key string) (ReactState, error)
	Save(ctx context.Context, row *ReactState) error
	DeleteForUser(ctx context.Context, userID uint, key string) error
}
