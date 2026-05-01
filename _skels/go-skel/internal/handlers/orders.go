// Order workflow handlers: catalog items, orders, order lines, order
// addresses, and status transitions (submit / approve / reject).
// Mirrors the same endpoint contract as the Flask, FastAPI, and
// django-bolt skeletons so cross-stack tests work unchanged.
//
// All database access goes through GORM — no raw SQL anywhere. The
// `time.Time` fields on the order/catalog models serialise as
// RFC3339 in JSON responses (uniform with the other backends).
package handlers

import (
	"errors"
	"net/http"
	"strconv"
	"time"

	"gorm.io/gorm"

	"github.com/example/go-skel/internal/auth"
	"github.com/example/go-skel/internal/models"
)

// --------------------------------------------------------------------------- //
//  JSON payloads (request bodies)
// --------------------------------------------------------------------------- //

type catalogItemPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
	Price       float64 `json:"price"`
	Category    *string `json:"category"`
	Available   *bool   `json:"available"`
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

// --------------------------------------------------------------------------- //
//  Order detail response (GORM models + nested children)
// --------------------------------------------------------------------------- //

// orderDetail is what GET /api/orders/{id}, submit, approve, and
// reject return. The base order fields come straight from the
// `Order` model; lines + address are queried separately and
// embedded in the JSON via the inline `,inline`-style anonymous
// composition.
type orderDetail struct {
	models.Order
	Lines   []models.OrderLine    `json:"lines"`
	Address *models.OrderAddress  `json:"address"`
}

// --------------------------------------------------------------------------- //
//  Catalog handlers
// --------------------------------------------------------------------------- //

func (d Deps) handleListCatalog(w http.ResponseWriter, r *http.Request) {
	var rows []models.CatalogItem
	if err := d.DB.WithContext(r.Context()).
		Order("id").Find(&rows).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "list catalog failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []models.CatalogItem{}
	}
	writeJSON(w, http.StatusOK, rows)
}

func (d Deps) handleCreateCatalogItem(w http.ResponseWriter, r *http.Request) {
	var body catalogItemPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if body.Name == "" {
		writeError(w, http.StatusBadRequest, "catalog item name cannot be empty")
		return
	}
	item := models.CatalogItem{
		Name:      body.Name,
		Price:     body.Price,
		Available: true,
	}
	if body.Description != nil {
		item.Description = *body.Description
	}
	if body.Category != nil {
		item.Category = *body.Category
	}
	if body.Available != nil {
		item.Available = *body.Available
	}
	if err := d.DB.WithContext(r.Context()).Create(&item).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "insert catalog item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, item)
}

func (d Deps) handleGetCatalogItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var item models.CatalogItem
	if err := d.DB.WithContext(r.Context()).First(&item, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "catalog item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch catalog item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

// --------------------------------------------------------------------------- //
//  Order CRUD
// --------------------------------------------------------------------------- //

func (d Deps) handleCreateOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	order := models.Order{UserID: uint(user.ID), Status: "draft"}
	if err := d.DB.WithContext(r.Context()).Create(&order).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "create order failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, order)
}

func (d Deps) handleListOrders(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	var rows []models.Order
	if err := d.DB.WithContext(r.Context()).
		Where("user_id = ?", user.ID).
		Order("created_at DESC, id DESC").
		Find(&rows).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "list orders failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []models.Order{}
	}
	writeJSON(w, http.StatusOK, rows)
}

func (d Deps) handleGetOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	detail, err := d.loadOrderDetail(r, id, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

// --------------------------------------------------------------------------- //
//  Order lines
// --------------------------------------------------------------------------- //

func (d Deps) handleAddOrderLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if order.Status != "draft" {
		writeError(w, http.StatusBadRequest, "can only add lines to draft orders")
		return
	}

	var body addLinePayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if body.CatalogItemID == 0 {
		writeError(w, http.StatusBadRequest, "catalog_item_id is required")
		return
	}
	if body.Quantity < 1 {
		body.Quantity = 1
	}

	var catItem models.CatalogItem
	if err := tx.First(&catItem, body.CatalogItemID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "catalog item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch catalog item failed: "+err.Error())
		return
	}

	line := models.OrderLine{
		OrderID:       orderID,
		CatalogItemID: body.CatalogItemID,
		Quantity:      body.Quantity,
		UnitPrice:     catItem.Price,
	}
	if err := tx.Create(&line).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "insert order line failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, line)
}

func (d Deps) handleDeleteOrderLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "order_id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	lineID, err := pathID(r, "line_id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if order.Status != "draft" {
		writeError(w, http.StatusBadRequest, "can only remove lines from draft orders")
		return
	}

	res := tx.Where("id = ? AND order_id = ?", lineID, orderID).
		Delete(&models.OrderLine{})
	if res.Error != nil {
		writeError(w, http.StatusInternalServerError, "delete order line failed: "+res.Error.Error())
		return
	}
	if res.RowsAffected == 0 {
		writeError(w, http.StatusNotFound, "order line not found")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// --------------------------------------------------------------------------- //
//  Order address
// --------------------------------------------------------------------------- //

func (d Deps) handleUpsertOrderAddress(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	tx := d.DB.WithContext(r.Context())
	if _, err := d.fetchOrderForUser(tx, orderID, uint(user.ID)); err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}

	var body addressPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}

	var addr models.OrderAddress
	err = tx.Where("order_id = ?", orderID).First(&addr).Error
	switch {
	case err == nil:
		addr.Street = body.Street
		addr.City = body.City
		addr.ZipCode = body.ZipCode
		addr.Phone = body.Phone
		addr.Notes = body.Notes
		if err := tx.Save(&addr).Error; err != nil {
			writeError(w, http.StatusInternalServerError, "update address failed: "+err.Error())
			return
		}
	case errors.Is(err, gorm.ErrRecordNotFound):
		addr = models.OrderAddress{
			OrderID: orderID,
			Street:  body.Street,
			City:    body.City,
			ZipCode: body.ZipCode,
			Phone:   body.Phone,
			Notes:   body.Notes,
		}
		if err := tx.Create(&addr).Error; err != nil {
			writeError(w, http.StatusInternalServerError, "insert address failed: "+err.Error())
			return
		}
	default:
		writeError(w, http.StatusInternalServerError, "fetch address failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, addr)
}

// --------------------------------------------------------------------------- //
//  Status transitions (submit / approve / reject)
// --------------------------------------------------------------------------- //

func (d Deps) handleSubmitOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if order.Status != "draft" {
		writeError(w, http.StatusBadRequest, "only draft orders can be submitted")
		return
	}
	var lineCount int64
	if err := tx.Model(&models.OrderLine{}).
		Where("order_id = ?", orderID).
		Count(&lineCount).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "count lines failed: "+err.Error())
		return
	}
	if lineCount == 0 {
		writeError(w, http.StatusBadRequest, "cannot submit an order with no lines")
		return
	}
	now := time.Now().UTC()
	order.Status = "pending"
	order.SubmittedAt = &now
	if err := tx.Save(&order).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "submit order failed: "+err.Error())
		return
	}
	d.writeOrderDetail(w, r, orderID, uint(user.ID))
}

func (d Deps) handleApproveOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if order.Status != "pending" {
		writeError(w, http.StatusBadRequest, "only submitted orders can be approved")
		return
	}
	var body approvePayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	order.Status = "approved"
	order.WaitMinutes = body.WaitMinutes
	order.Feedback = body.Feedback
	if err := tx.Save(&order).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "approve order failed: "+err.Error())
		return
	}
	d.writeOrderDetail(w, r, orderID, uint(user.ID))
}

func (d Deps) handleRejectOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, uint(user.ID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if order.Status != "pending" {
		writeError(w, http.StatusBadRequest, "only submitted orders can be rejected")
		return
	}
	var body rejectPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	order.Status = "rejected"
	order.Feedback = body.Feedback
	if err := tx.Save(&order).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "reject order failed: "+err.Error())
		return
	}
	d.writeOrderDetail(w, r, orderID, uint(user.ID))
}

// --------------------------------------------------------------------------- //
//  Helpers
// --------------------------------------------------------------------------- //

// fetchOrderForUser fetches an order by id and verifies it belongs to
// the given user. Returns gorm.ErrRecordNotFound when not found OR
// not owned (so callers map both to 404).
func (d Deps) fetchOrderForUser(tx *gorm.DB, orderID, userID uint) (models.Order, error) {
	var o models.Order
	if err := tx.First(&o, orderID).Error; err != nil {
		return o, err
	}
	if o.UserID != userID {
		return o, gorm.ErrRecordNotFound
	}
	return o, nil
}

// loadOrderDetail builds the orderDetail (order + lines + address)
// for the given user-owned order. Returns gorm.ErrRecordNotFound
// when the order does not exist or is owned by a different user.
func (d Deps) loadOrderDetail(r *http.Request, orderID, userID uint) (orderDetail, error) {
	tx := d.DB.WithContext(r.Context())
	order, err := d.fetchOrderForUser(tx, orderID, userID)
	if err != nil {
		return orderDetail{}, err
	}

	var lines []models.OrderLine
	if err := tx.Where("order_id = ?", orderID).Find(&lines).Error; err != nil {
		return orderDetail{}, err
	}
	if lines == nil {
		lines = []models.OrderLine{}
	}

	var address *models.OrderAddress
	var addr models.OrderAddress
	addrErr := tx.Where("order_id = ?", orderID).First(&addr).Error
	switch {
	case addrErr == nil:
		address = &addr
	case errors.Is(addrErr, gorm.ErrRecordNotFound):
		address = nil
	default:
		return orderDetail{}, addrErr
	}

	return orderDetail{Order: order, Lines: lines, Address: address}, nil
}

func (d Deps) writeOrderDetail(w http.ResponseWriter, r *http.Request, orderID, userID uint) {
	detail, err := d.loadOrderDetail(r, orderID, userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "refetch order failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, detail)
}

// strconv is imported indirectly via pathID's caller above. Keep a
// stub reference so goimports does not strip the package import on
// editors that auto-format aggressively.
var _ = strconv.Itoa
