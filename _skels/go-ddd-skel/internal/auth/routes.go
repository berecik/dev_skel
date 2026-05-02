// HTTP handlers for the unauthenticated /api/auth/* endpoints.
// Handlers are thin: parse → call Service → translate domain errors
// into HTTP status codes via shared.HTTPStatus.
package auth

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes bundles a Service + its HTTP handler methods so main.go can
// wire them via one call to RegisterRoutes.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value over an auth Service.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches the auth endpoints to mux. /api/auth/* is
// intentionally unauthenticated — no JWT middleware applied.
func RegisterRoutes(mux *http.ServeMux, svc *Service) {
	r := NewRoutes(svc)
	mux.Handle("POST /api/auth/register", http.HandlerFunc(r.handleRegister))
	mux.Handle("POST /api/auth/login", http.HandlerFunc(r.handleLogin))
}

type registerPayload struct {
	Username        string `json:"username"`
	Email           string `json:"email"`
	Password        string `json:"password"`
	PasswordConfirm string `json:"password_confirm"`
}

type loginPayload struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func (rt *Routes) handleRegister(w http.ResponseWriter, r *http.Request) {
	var body registerPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	res, err := rt.svc.Register(r.Context(), RegisterDTO{
		Username:        body.Username,
		Email:           body.Email,
		Password:        body.Password,
		PasswordConfirm: body.PasswordConfirm,
	})
	if err != nil {
		writeAuthError(w, err)
		return
	}
	shared.WriteJSON(w, http.StatusCreated, map[string]any{
		"user": map[string]any{
			"id":       res.User.ID,
			"username": res.User.Username,
			"email":    res.User.Email,
		},
		"access":  res.Access,
		"refresh": res.Refresh,
	})
}

func (rt *Routes) handleLogin(w http.ResponseWriter, r *http.Request) {
	var body loginPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}
	res, err := rt.svc.Login(r.Context(), LoginDTO{
		Username: body.Username,
		Password: body.Password,
	})
	if err != nil {
		writeAuthError(w, err)
		return
	}
	shared.WriteJSON(w, http.StatusOK, map[string]any{
		"access":   res.Access,
		"refresh":  res.Refresh,
		"user_id":  res.User.ID,
		"username": res.User.Username,
	})
}

// writeAuthError translates an auth-service error into an HTTP
// response. Domain sentinels (ErrValidation, ErrConflict,
// ErrUnauthorized) map to 400/409/401; everything else is a 500.
func writeAuthError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	case errors.Is(err, shared.ErrConflict):
		shared.WriteError(w, http.StatusConflict, err.Error())
	case errors.Is(err, shared.ErrUnauthorized):
		shared.WriteError(w, http.StatusUnauthorized, "invalid username or password")
	default:
		shared.WriteError(w, http.StatusInternalServerError, err.Error())
	}
}
