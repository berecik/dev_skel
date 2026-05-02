// HTTP handlers for /api/catalog.
package catalog

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes binds a catalog.Service to the HTTP layer.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches every /api/catalog endpoint to mux.
func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler) {
	r := NewRoutes(svc)
	mux.Handle("GET /api/catalog", jwt(http.HandlerFunc(r.handleList)))
	mux.Handle("POST /api/catalog", jwt(http.HandlerFunc(r.handleCreate)))
	mux.Handle("GET /api/catalog/{id}", jwt(http.HandlerFunc(r.handleGet)))
}

type catalogItemPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
	Price       float64 `json:"price"`
	Category    *string `json:"category"`
	Available   *bool   `json:"available"`
}

func (h *Routes) handleList(w http.ResponseWriter, r *http.Request) {
	rows, err := h.svc.List(r.Context())
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "list catalog failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []CatalogItem{}
	}
	shared.WriteJSON(w, http.StatusOK, rows)
}

func (h *Routes) handleCreate(w http.ResponseWriter, r *http.Request) {
	var body catalogItemPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	item, err := h.svc.Create(r.Context(), CreateCatalogItemDTO{
		Name:        body.Name,
		Description: body.Description,
		Price:       body.Price,
		Category:    body.Category,
		Available:   body.Available,
	})
	if err != nil {
		writeCatalogError(w, err, "insert catalog item failed")
		return
	}
	shared.WriteJSON(w, http.StatusCreated, item)
}

func (h *Routes) handleGet(w http.ResponseWriter, r *http.Request) {
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	item, err := h.svc.Get(r.Context(), id)
	if err != nil {
		writeCatalogError(w, err, "fetch catalog item failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, item)
}

func writeCatalogError(w http.ResponseWriter, err error, fallback string) {
	switch {
	case errors.Is(err, shared.ErrNotFound):
		shared.WriteError(w, http.StatusNotFound, "catalog item not found")
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	default:
		shared.WriteError(w, http.StatusInternalServerError, fallback+": "+err.Error())
	}
}
