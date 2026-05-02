// Package users wraps the User entity with a repository abstraction
// the auth + seed packages depend on. Auth handlers go through
// UserService.Register / Authenticate so the GORM bits stay confined
// to users/adapters.
package users

import (
	"context"

	"github.com/example/go-ddd-skel/internal/models"
)

// User is the canonical entity (re-exported from internal/models so
// callers stay decoupled from the GORM tags).
type User = models.User

// CreateUserDTO is the input shape for Register. Mirrors the
// FastAPI pilot's CreateItemDTO style: separate input DTOs from the
// entity so request parsing has its own type to validate.
type CreateUserDTO struct {
	Username     string
	Email        string
	PasswordHash string
}

// Repository is the user-specific extension of shared.Repository[User].
// The auth + seed packages depend on this interface only — never on
// *gorm.DB directly.
type Repository interface {
	List(ctx context.Context) ([]User, error)
	Get(ctx context.Context, id uint) (User, error)
	GetByUsername(ctx context.Context, username string) (User, error)
	GetByEmail(ctx context.Context, email string) (User, error)
	Save(ctx context.Context, user *User) error
	Delete(ctx context.Context, id uint) error
}
