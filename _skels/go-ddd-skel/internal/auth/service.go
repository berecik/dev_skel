// Service-layer logic for the unauthenticated /api/auth/* endpoints
// (register + login). Talks to users.Repository for persistence and
// to the JWT mint helpers in this package for token issuance.
package auth

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/example/go-ddd-skel/internal/config"
	"github.com/example/go-ddd-skel/internal/models"
	"github.com/example/go-ddd-skel/internal/shared"
	"github.com/example/go-ddd-skel/internal/users"
)

// RegisterDTO is the create-user payload (mirrors the wrapper-shared
// /api/auth/register contract).
type RegisterDTO struct {
	Username        string
	Email           string
	Password        string
	PasswordConfirm string
}

// LoginDTO is the /api/auth/login payload (username may be either a
// username or an email).
type LoginDTO struct {
	Username string
	Password string
}

// AuthResult is the response returned by Register + Login.
type AuthResult struct {
	User    models.User
	Access  string
	Refresh string
}

// Service coordinates user creation + credential checks for the
// auth endpoints. It is the only thing in the auth package that
// holds a users.Repository plus a Config.
type Service struct {
	cfg   config.Config
	users users.Repository
}

// NewService constructs an auth Service. Wired from main.go.
func NewService(cfg config.Config, repo users.Repository) *Service {
	return &Service{cfg: cfg, users: repo}
}

// Register creates a fresh user (rejecting duplicates), hashes the
// password, and mints an access + refresh token pair. Returns a
// shared.ErrValidation / shared.ErrConflict on input issues so
// routes.go can map to 400 / 409 respectively.
func (s *Service) Register(ctx context.Context, dto RegisterDTO) (AuthResult, error) {
	if strings.TrimSpace(dto.Username) == "" {
		return AuthResult{}, fmt.Errorf("%w: username cannot be empty", shared.ErrValidation)
	}
	if len(dto.Password) < 6 {
		return AuthResult{}, fmt.Errorf("%w: password must be at least 6 characters", shared.ErrValidation)
	}
	if dto.PasswordConfirm != "" && dto.PasswordConfirm != dto.Password {
		return AuthResult{}, fmt.Errorf("%w: password and password_confirm do not match", shared.ErrValidation)
	}

	if _, err := s.users.GetByUsername(ctx, dto.Username); err == nil {
		return AuthResult{}, fmt.Errorf("%w: user '%s' already exists", shared.ErrConflict, dto.Username)
	} else if !errors.Is(err, shared.ErrNotFound) {
		return AuthResult{}, err
	}

	hashed, err := HashPassword(dto.Password)
	if err != nil {
		return AuthResult{}, err
	}
	user := models.User{
		Username:     dto.Username,
		Email:        dto.Email,
		PasswordHash: hashed,
	}
	if err := s.users.Save(ctx, &user); err != nil {
		return AuthResult{}, err
	}

	access, err := MintAccessToken(s.cfg, int64(user.ID))
	if err != nil {
		return AuthResult{}, err
	}
	refresh, err := MintRefreshToken(s.cfg, int64(user.ID))
	if err != nil {
		return AuthResult{}, err
	}
	return AuthResult{User: user, Access: access, Refresh: refresh}, nil
}

// Login validates the supplied credentials and returns a fresh token
// pair. Returns shared.ErrUnauthorized on every failure so the
// caller can map to a 401 without leaking which field was wrong.
func (s *Service) Login(ctx context.Context, dto LoginDTO) (AuthResult, error) {
	if dto.Username == "" || dto.Password == "" {
		return AuthResult{}, fmt.Errorf("%w: invalid username or password", shared.ErrUnauthorized)
	}

	var (
		user users.User
		err  error
	)
	if strings.Contains(dto.Username, "@") {
		user, err = s.users.GetByEmail(ctx, dto.Username)
	} else {
		user, err = s.users.GetByUsername(ctx, dto.Username)
	}
	if err != nil {
		return AuthResult{}, fmt.Errorf("%w: invalid username or password", shared.ErrUnauthorized)
	}
	if !VerifyPassword(dto.Password, user.PasswordHash) {
		return AuthResult{}, fmt.Errorf("%w: invalid username or password", shared.ErrUnauthorized)
	}

	access, err := MintAccessToken(s.cfg, int64(user.ID))
	if err != nil {
		return AuthResult{}, err
	}
	refresh, err := MintRefreshToken(s.cfg, int64(user.ID))
	if err != nil {
		return AuthResult{}, err
	}
	return AuthResult{User: user, Access: access, Refresh: refresh}, nil
}
