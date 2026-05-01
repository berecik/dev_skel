// Package auth handles JWT mint/verify, password hashing, and the
// HTTP middleware that gates `/api/items` and `/api/state` on a
// valid Bearer token. Token format matches the rest of the dev_skel
// backends (HS256, iss=devskel, sub=<user_id>) so a token issued by
// django-bolt or fastapi is accepted here unchanged.
package auth

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"

	"github.com/example/go-skel/internal/config"
	"github.com/example/go-skel/internal/models"
)

// User is the authenticated principal published into the request
// context by the JWT middleware. Handlers that need the caller's
// identity pull it out via UserFromContext.
type User struct {
	ID       int64
	Username string
}

type ctxKey string

const userContextKey ctxKey = "auth.user"

// HashPassword returns a bcrypt hash of the plaintext password.
func HashPassword(plaintext string) (string, error) {
	hashed, err := bcrypt.GenerateFromPassword([]byte(plaintext), bcrypt.DefaultCost)
	if err != nil {
		return "", err
	}
	return string(hashed), nil
}

// VerifyPassword compares plaintext to a bcrypt hash. Returns true on
// match; never panics on a malformed hash.
func VerifyPassword(plaintext, hashed string) bool {
	if hashed == "" {
		return false
	}
	return bcrypt.CompareHashAndPassword([]byte(hashed), []byte(plaintext)) == nil
}

func signingMethod(name string) jwt.SigningMethod {
	switch strings.ToUpper(name) {
	case "HS384":
		return jwt.SigningMethodHS384
	case "HS512":
		return jwt.SigningMethodHS512
	default:
		// Anything we don't recognise falls back to HS256 — that is
		// the wrapper-shared default and the python skels hard-pin it.
		return jwt.SigningMethodHS256
	}
}

// MintAccessToken returns a freshly-signed access token for userID.
func MintAccessToken(cfg config.Config, userID int64) (string, error) {
	return mintToken(cfg, userID, time.Duration(cfg.JWTAccessTTL)*time.Second, "")
}

// MintRefreshToken returns a freshly-signed refresh token for userID
// (carries `token_type=refresh` so the middleware can reject it).
func MintRefreshToken(cfg config.Config, userID int64) (string, error) {
	return mintToken(cfg, userID, time.Duration(cfg.JWTRefreshTTL)*time.Second, "refresh")
}

func mintToken(cfg config.Config, userID int64, ttl time.Duration, tokenType string) (string, error) {
	now := time.Now()
	claims := jwt.MapClaims{
		"sub": strconv.FormatInt(userID, 10),
		"iss": cfg.JWTIssuer,
		"iat": now.Unix(),
		"exp": now.Add(ttl).Unix(),
	}
	if tokenType != "" {
		claims["token_type"] = tokenType
	}
	tok := jwt.NewWithClaims(signingMethod(cfg.JWTAlgorithm), claims)
	return tok.SignedString([]byte(cfg.JWTSecret))
}

// verifyToken parses and validates a token. Returns the user id, the
// token-type claim (empty for access tokens), and any error.
func verifyToken(cfg config.Config, raw string) (int64, string, error) {
	method := signingMethod(cfg.JWTAlgorithm)
	parsed, err := jwt.Parse(raw, func(t *jwt.Token) (interface{}, error) {
		if t.Method.Alg() != method.Alg() {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(cfg.JWTSecret), nil
	}, jwt.WithIssuer(cfg.JWTIssuer))
	if err != nil {
		return 0, "", err
	}
	claims, ok := parsed.Claims.(jwt.MapClaims)
	if !ok || !parsed.Valid {
		return 0, "", errors.New("invalid token")
	}
	subRaw, ok := claims["sub"].(string)
	if !ok {
		return 0, "", errors.New("malformed sub claim")
	}
	userID, err := strconv.ParseInt(subRaw, 10, 64)
	if err != nil {
		return 0, "", errors.New("malformed sub claim")
	}
	tokenType, _ := claims["token_type"].(string)
	return userID, tokenType, nil
}

// Middleware returns an http.Handler middleware that enforces a
// valid Bearer JWT on the wrapped handler. The authenticated User is
// published into the request context via UserFromContext.
func Middleware(cfg config.Config, db *gorm.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			header := r.Header.Get("Authorization")
			if !strings.HasPrefix(header, "Bearer ") {
				writeUnauthorized(w, "missing or malformed Authorization header")
				return
			}
			token := strings.TrimSpace(strings.TrimPrefix(header, "Bearer "))
			userID, tokenType, err := verifyToken(cfg, token)
			if err != nil {
				writeUnauthorized(w, "invalid or expired token")
				return
			}
			if tokenType == "refresh" {
				writeUnauthorized(w, "refresh token cannot authenticate this request")
				return
			}
			var record models.User
			if err := db.WithContext(r.Context()).
				Select("id", "username").
				First(&record, userID).Error; err != nil {
				writeUnauthorized(w, "user no longer exists")
				return
			}
			ctx := context.WithValue(r.Context(), userContextKey, User{
				ID:       int64(record.ID),
				Username: record.Username,
			})
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// UserFromContext extracts the authenticated user populated by the
// middleware. Returns the zero value + false when the route was
// served outside the middleware (handlers should never see this for
// JWT-protected paths).
func UserFromContext(ctx context.Context) (User, bool) {
	u, ok := ctx.Value(userContextKey).(User)
	return u, ok
}

func writeUnauthorized(w http.ResponseWriter, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"detail": detail,
		"status": http.StatusUnauthorized,
	})
}
