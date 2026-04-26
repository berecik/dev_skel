// Package seed creates default user accounts from environment variables
// at startup. Each account is only inserted when no row with the same
// username exists, so the function is safe to call on every boot.
package seed

import (
	"context"
	"database/sql"
	"log"
	"os"

	"github.com/example/go-skel/internal/auth"
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
// inserts the corresponding rows into the users table when they do
// not already exist.
func SeedDefaultAccounts(ctx context.Context, db *sql.DB) error {
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

		var count int
		if err := db.QueryRowContext(ctx,
			`SELECT COUNT(*) FROM users WHERE username = ?`, login,
		).Scan(&count); err != nil {
			return err
		}
		if count > 0 {
			log.Printf("seed: user %q already exists, skipping", login)
			continue
		}

		hashed, err := auth.HashPassword(password)
		if err != nil {
			return err
		}
		if _, err := db.ExecContext(ctx,
			`INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)`,
			login, email, hashed,
		); err != nil {
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
