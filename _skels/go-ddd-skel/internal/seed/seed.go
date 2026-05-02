// Package seed creates default user accounts from environment variables
// at startup. Each account is only inserted when no row with the same
// username exists, so the function is safe to call on every boot.
//
// Persistence goes through users.Repository so the seed flow does not
// touch *gorm.DB directly — same abstraction the auth + middleware
// layers use.
package seed

import (
	"context"
	"errors"
	"log"
	"os"

	"github.com/example/go-ddd-skel/internal/auth"
	"github.com/example/go-ddd-skel/internal/models"
	"github.com/example/go-ddd-skel/internal/shared"
	"github.com/example/go-ddd-skel/internal/users"
)

// account describes a single default user to seed.
type account struct {
	loginEnv    string
	emailEnv    string
	passwordEnv string
	loginDef    string
	emailDef    string
	passwordDef string
}

// SeedDefaultAccounts reads USER_* and SUPERUSER_* env vars and
// inserts the corresponding rows via the supplied users.Repository
// when they do not already exist.
func SeedDefaultAccounts(ctx context.Context, repo users.Repository) error {
	accounts := []account{
		{
			loginEnv:    "USER_LOGIN",
			emailEnv:    "USER_EMAIL",
			passwordEnv: "USER_PASSWORD",
			loginDef:    "user",
			emailDef:    "user@example.com",
			passwordDef: "secret",
		},
		{
			loginEnv:    "SUPERUSER_LOGIN",
			emailEnv:    "SUPERUSER_EMAIL",
			passwordEnv: "SUPERUSER_PASSWORD",
			loginDef:    "admin",
			emailDef:    "admin@example.com",
			passwordDef: "secret",
		},
	}

	for _, a := range accounts {
		login := envOr(a.loginEnv, a.loginDef)
		email := envOr(a.emailEnv, a.emailDef)
		password := envOr(a.passwordEnv, a.passwordDef)

		_, err := repo.GetByUsername(ctx, login)
		if err == nil {
			log.Printf("seed: user %q already exists, skipping", login)
			continue
		}
		if !errors.Is(err, shared.ErrNotFound) {
			return err
		}

		hashed, err := auth.HashPassword(password)
		if err != nil {
			return err
		}
		user := models.User{
			Username:     login,
			Email:        email,
			PasswordHash: hashed,
		}
		if err := repo.Save(ctx, &user); err != nil {
			return err
		}
		log.Printf("seed: created default user %q (%s)", login, email)
	}
	return nil
}

// envOr returns the value of the environment variable named key, or
// fallback when the variable is unset or empty.
func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
