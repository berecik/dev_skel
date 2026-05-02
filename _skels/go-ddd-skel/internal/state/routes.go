// HTTP handlers for /api/state.
package state

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/auth"
	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes binds a state.Service to the HTTP layer.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches every /api/state endpoint to mux.
func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler) {
	r := NewRoutes(svc)
	mux.Handle("GET /api/state", jwt(http.HandlerFunc(r.handleList)))
	mux.Handle("PUT /api/state/{key}", jwt(http.HandlerFunc(r.handleUpsert)))
	mux.Handle("DELETE /api/state/{key}", jwt(http.HandlerFunc(r.handleDelete)))
}

type upsertStatePayload struct {
	Value string `json:"value"`
}

func (h *Routes) handleList(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	out, err := h.svc.Map(r.Context(), uint(user.ID))
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "list state failed: "+err.Error())
		return
	}
	shared.WriteJSON(w, http.StatusOK, out)
}

func (h *Routes) handleUpsert(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	key := r.PathValue("key")
	if key == "" {
		shared.WriteError(w, http.StatusBadRequest, "state key cannot be empty")
		return
	}
	var body upsertStatePayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if err := h.svc.Upsert(r.Context(), uint(user.ID), key, body.Value); err != nil {
		writeStateError(w, err, "upsert state failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, map[string]any{"key": key})
}

func (h *Routes) handleDelete(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	key := r.PathValue("key")
	if key == "" {
		shared.WriteError(w, http.StatusBadRequest, "state key cannot be empty")
		return
	}
	if err := h.svc.Delete(r.Context(), uint(user.ID), key); err != nil {
		writeStateError(w, err, "delete state failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, map[string]any{})
}

func writeStateError(w http.ResponseWriter, err error, fallback string) {
	switch {
	case errors.Is(err, shared.ErrNotFound):
		shared.WriteError(w, http.StatusNotFound, "state not found")
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	default:
		shared.WriteError(w, http.StatusInternalServerError, fallback+": "+err.Error())
	}
}
