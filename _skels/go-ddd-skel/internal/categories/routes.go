// HTTP handlers for /api/categories.
package categories

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes binds a categories.Service to the HTTP layer.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches every /api/categories endpoint to mux.
func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler) {
	r := NewRoutes(svc)
	mux.Handle("GET /api/categories", jwt(http.HandlerFunc(r.handleList)))
	mux.Handle("POST /api/categories", jwt(http.HandlerFunc(r.handleCreate)))
	mux.Handle("GET /api/categories/{id}", jwt(http.HandlerFunc(r.handleGet)))
	mux.Handle("PUT /api/categories/{id}", jwt(http.HandlerFunc(r.handleUpdate)))
	mux.Handle("DELETE /api/categories/{id}", jwt(http.HandlerFunc(r.handleDelete)))
}

type categoryPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
}

func (h *Routes) handleList(w http.ResponseWriter, r *http.Request) {
	rows, err := h.svc.List(r.Context())
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "list categories failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []Category{}
	}
	shared.WriteJSON(w, http.StatusOK, rows)
}

func (h *Routes) handleCreate(w http.ResponseWriter, r *http.Request) {
	var body categoryPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	c, err := h.svc.Create(r.Context(), CategoryDTO{Name: body.Name, Description: body.Description})
	if err != nil {
		writeCategoryError(w, err, "insert category failed")
		return
	}
	shared.WriteJSON(w, http.StatusCreated, c)
}

func (h *Routes) handleGet(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	c, err := h.svc.Get(r.Context(), id)
	if err != nil {
		writeCategoryError(w, err, "fetch category failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, c)
}

func (h *Routes) handleUpdate(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body categoryPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	c, err := h.svc.Update(r.Context(), id, CategoryDTO{Name: body.Name, Description: body.Description})
	if err != nil {
		writeCategoryError(w, err, "update category failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, c)
}

func (h *Routes) handleDelete(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.svc.Delete(r.Context(), id); err != nil {
		writeCategoryError(w, err, "delete category failed")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func writeCategoryError(w http.ResponseWriter, err error, fallback string) {
	switch {
	case errors.Is(err, shared.ErrNotFound):
		shared.WriteError(w, http.StatusNotFound, "category not found")
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	case errors.Is(err, shared.ErrConflict):
		shared.WriteError(w, http.StatusConflict, err.Error())
	default:
		shared.WriteError(w, http.StatusInternalServerError, fallback+": "+err.Error())
	}
}
