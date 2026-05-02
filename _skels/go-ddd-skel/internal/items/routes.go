// HTTP handlers for /api/items. Thin: parse → call Service →
// translate domain errors via shared.HTTPStatus.
package items

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes binds an items.Service to the HTTP layer.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches every /api/items endpoint to mux. The
// supplied middleware chain is applied to every route (typically the
// JWT bearer-token gate from the auth package).
func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler) {
	r := NewRoutes(svc)
	mux.Handle("GET /api/items", jwt(http.HandlerFunc(r.handleListItems)))
	mux.Handle("POST /api/items", jwt(http.HandlerFunc(r.handleCreateItem)))
	mux.Handle("GET /api/items/{id}", jwt(http.HandlerFunc(r.handleGetItem)))
	mux.Handle("POST /api/items/{id}/complete", jwt(http.HandlerFunc(r.handleCompleteItem)))
}

type itemPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
	IsCompleted bool    `json:"is_completed"`
	CategoryID  *uint   `json:"category_id"`
}

func (h *Routes) handleListItems(w http.ResponseWriter, r *http.Request) {
	rows, err := h.svc.List(r.Context())
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "list items failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []Item{}
	}
	shared.WriteJSON(w, http.StatusOK, rows)
}

func (h *Routes) handleCreateItem(w http.ResponseWriter, r *http.Request) {
	var body itemPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	dto := CreateItemDTO{
		Name:        body.Name,
		IsCompleted: body.IsCompleted,
		CategoryID:  body.CategoryID,
	}
	if body.Description != nil {
		dto.Description = *body.Description
	}
	item, err := h.svc.Create(r.Context(), dto)
	if err != nil {
		writeItemError(w, err, "insert item failed")
		return
	}
	shared.WriteJSON(w, http.StatusCreated, item)
}

func (h *Routes) handleGetItem(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	item, err := h.svc.Get(r.Context(), id)
	if err != nil {
		writeItemError(w, err, "fetch item failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, item)
}

func (h *Routes) handleCompleteItem(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	item, err := h.svc.Complete(r.Context(), id)
	if err != nil {
		writeItemError(w, err, "complete item failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, item)
}

// writeItemError maps domain errors to HTTP responses. NotFound →
// 404 with the canonical message; Validation → 400; everything else
// → 500 prefixed with the supplied operation label.
func writeItemError(w http.ResponseWriter, err error, fallback string) {
	switch {
	case errors.Is(err, shared.ErrNotFound):
		shared.WriteError(w, http.StatusNotFound, "item not found")
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	case errors.Is(err, shared.ErrConflict):
		shared.WriteError(w, http.StatusConflict, err.Error())
	default:
		shared.WriteError(w, http.StatusInternalServerError, fallback+": "+err.Error())
	}
}
