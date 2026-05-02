// HTTP handlers for /api/orders.
package orders

import (
	"errors"
	"net/http"

	"github.com/example/go-ddd-skel/internal/auth"
	"github.com/example/go-ddd-skel/internal/shared"
)

// Routes binds an orders.Service to the HTTP layer.
type Routes struct {
	svc *Service
}

// NewRoutes constructs a Routes value.
func NewRoutes(svc *Service) *Routes {
	return &Routes{svc: svc}
}

// RegisterRoutes attaches every /api/orders endpoint to mux.
func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler) {
	r := NewRoutes(svc)
	mux.Handle("POST /api/orders", jwt(http.HandlerFunc(r.handleCreate)))
	mux.Handle("GET /api/orders", jwt(http.HandlerFunc(r.handleList)))
	mux.Handle("GET /api/orders/{id}", jwt(http.HandlerFunc(r.handleGet)))
	mux.Handle("POST /api/orders/{id}/lines", jwt(http.HandlerFunc(r.handleAddLine)))
	mux.Handle("DELETE /api/orders/{order_id}/lines/{line_id}", jwt(http.HandlerFunc(r.handleDeleteLine)))
	mux.Handle("PUT /api/orders/{id}/address", jwt(http.HandlerFunc(r.handleUpsertAddress)))
	mux.Handle("POST /api/orders/{id}/submit", jwt(http.HandlerFunc(r.handleSubmit)))
	mux.Handle("POST /api/orders/{id}/approve", jwt(http.HandlerFunc(r.handleApprove)))
	mux.Handle("POST /api/orders/{id}/reject", jwt(http.HandlerFunc(r.handleReject)))
}

type addLinePayload struct {
	CatalogItemID uint `json:"catalog_item_id"`
	Quantity      int  `json:"quantity"`
}

type addressPayload struct {
	Street  string  `json:"street"`
	City    string  `json:"city"`
	ZipCode string  `json:"zip_code"`
	Phone   *string `json:"phone"`
	Notes   *string `json:"notes"`
}

type approvePayload struct {
	WaitMinutes *int    `json:"wait_minutes"`
	Feedback    *string `json:"feedback"`
}

type rejectPayload struct {
	Feedback *string `json:"feedback"`
}

func (h *Routes) handleCreate(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	order, err := h.svc.CreateOrder(r.Context(), uint(user.ID))
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "create order failed: "+err.Error())
		return
	}
	shared.WriteJSON(w, http.StatusCreated, order)
}

func (h *Routes) handleList(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	rows, err := h.svc.ListOrders(r.Context(), uint(user.ID))
	if err != nil {
		shared.WriteError(w, http.StatusInternalServerError, "list orders failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []Order{}
	}
	shared.WriteJSON(w, http.StatusOK, rows)
}

func (h *Routes) handleGet(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	id, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	detail, err := h.svc.GetDetail(r.Context(), id, uint(user.ID))
	if err != nil {
		writeOrderError(w, err, "fetch order failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, detail)
}

func (h *Routes) handleAddLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body addLinePayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	line, err := h.svc.AddLine(r.Context(), orderID, uint(user.ID), AddLineDTO{
		CatalogItemID: body.CatalogItemID,
		Quantity:      body.Quantity,
	})
	if err != nil {
		writeOrderError(w, err, "insert order line failed")
		return
	}
	shared.WriteJSON(w, http.StatusCreated, line)
}

func (h *Routes) handleDeleteLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "order_id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	lineID, err := shared.PathID(r, "line_id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.svc.DeleteLine(r.Context(), orderID, uint(user.ID), lineID); err != nil {
		writeOrderError(w, err, "delete order line failed")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *Routes) handleUpsertAddress(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body addressPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	addr, err := h.svc.UpsertAddress(r.Context(), orderID, uint(user.ID), AddressDTO{
		Street:  body.Street,
		City:    body.City,
		ZipCode: body.ZipCode,
		Phone:   body.Phone,
		Notes:   body.Notes,
	})
	if err != nil {
		writeOrderError(w, err, "upsert address failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, addr)
}

func (h *Routes) handleSubmit(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	detail, err := h.svc.Submit(r.Context(), orderID, uint(user.ID))
	if err != nil {
		writeOrderError(w, err, "submit order failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, detail)
}

func (h *Routes) handleApprove(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body approvePayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	detail, err := h.svc.Approve(r.Context(), orderID, uint(user.ID), ApproveDTO{
		WaitMinutes: body.WaitMinutes,
		Feedback:    body.Feedback,
	})
	if err != nil {
		writeOrderError(w, err, "approve order failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, detail)
}

func (h *Routes) handleReject(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := shared.PathID(r, "id")
	if err != nil {
		shared.WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body rejectPayload
	if err := shared.DecodeJSON(r, &body); err != nil {
		shared.WriteError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	detail, err := h.svc.Reject(r.Context(), orderID, uint(user.ID), RejectDTO{
		Feedback: body.Feedback,
	})
	if err != nil {
		writeOrderError(w, err, "reject order failed")
		return
	}
	shared.WriteJSON(w, http.StatusOK, detail)
}

func writeOrderError(w http.ResponseWriter, err error, fallback string) {
	switch {
	case errors.Is(err, shared.ErrNotFound):
		shared.WriteError(w, http.StatusNotFound, "order not found")
	case errors.Is(err, shared.ErrValidation):
		shared.WriteError(w, http.StatusBadRequest, err.Error())
	case errors.Is(err, shared.ErrConflict):
		shared.WriteError(w, http.StatusConflict, err.Error())
	default:
		shared.WriteError(w, http.StatusInternalServerError, fallback+": "+err.Error())
	}
}
