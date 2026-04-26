// Order workflow handlers: catalog items, orders, order lines, order
// addresses, and status transitions (submit / approve / reject).
// Mirrors the same endpoint contract as the Flask, FastAPI, and
// django-bolt skeletons so cross-stack tests work unchanged.
package handlers

import (
	"database/sql"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/example/go-skel/internal/auth"
)

// --------------------------------------------------------------------------- //
//  JSON payloads (request bodies)
// --------------------------------------------------------------------------- //

type catalogItemPayload struct {
	Name        string   `json:"name"`
	Description *string  `json:"description"`
	Price       float64  `json:"price"`
	Category    *string  `json:"category"`
	Available   *bool    `json:"available"`
}

type addLinePayload struct {
	CatalogItemID int64 `json:"catalog_item_id"`
	Quantity      int   `json:"quantity"`
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
//  Response structs
// --------------------------------------------------------------------------- //

type catalogItemResponse struct {
	ID          int64   `json:"id"`
	Name        string  `json:"name"`
	Description *string `json:"description"`
	Price       string  `json:"price"`
	Category    *string `json:"category"`
	Available   bool    `json:"available"`
	CreatedAt   string  `json:"created_at"`
	UpdatedAt   string  `json:"updated_at"`
}

type orderResponse struct {
	ID           int64   `json:"id"`
	UserID       int64   `json:"user_id"`
	Status       string  `json:"status"`
	CreatedAt    string  `json:"created_at"`
	SubmittedAt  *string `json:"submitted_at"`
	WaitMinutes  *int    `json:"wait_minutes"`
	Feedback     *string `json:"feedback"`
}

type orderLineResponse struct {
	ID            int64  `json:"id"`
	OrderID       int64  `json:"order_id"`
	CatalogItemID int64  `json:"catalog_item_id"`
	Quantity      int    `json:"quantity"`
	UnitPrice     string `json:"unit_price"`
}

type orderAddressResponse struct {
	ID      int64  `json:"id"`
	OrderID int64  `json:"order_id"`
	Street  string `json:"street"`
	City    string `json:"city"`
	ZipCode string `json:"zip_code"`
	Phone   string `json:"phone"`
	Notes   string `json:"notes"`
}

type orderDetailResponse struct {
	ID           int64                 `json:"id"`
	UserID       int64                 `json:"user_id"`
	Status       string                `json:"status"`
	CreatedAt    string                `json:"created_at"`
	SubmittedAt  *string               `json:"submitted_at"`
	WaitMinutes  *int                  `json:"wait_minutes"`
	Feedback     *string               `json:"feedback"`
	Lines        []orderLineResponse   `json:"lines"`
	Address      *orderAddressResponse `json:"address"`
}

// --------------------------------------------------------------------------- //
//  Catalog handlers
// --------------------------------------------------------------------------- //

func (d Deps) handleListCatalog(w http.ResponseWriter, r *http.Request) {
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, name, description, price, created_at, updated_at
		   FROM catalog_items ORDER BY id`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "list catalog failed: "+err.Error())
		return
	}
	defer rows.Close()
	out := []catalogItemResponse{}
	for rows.Next() {
		var c catalogItemResponse
		if err := rows.Scan(&c.ID, &c.Name, &c.Description, &c.Price, &c.CreatedAt, &c.UpdatedAt); err != nil {
			writeError(w, http.StatusInternalServerError, "scan catalog item failed: "+err.Error())
			return
		}
		out = append(out, c)
	}
	if err := rows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (d Deps) handleCreateCatalogItem(w http.ResponseWriter, r *http.Request) {
	var body catalogItemPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "catalog item name cannot be empty")
		return
	}
	desc := ""
	if body.Description != nil {
		desc = *body.Description
	}
	cat := ""
	if body.Category != nil {
		cat = *body.Category
	}
	avail := true
	if body.Available != nil {
		avail = *body.Available
	}
	availInt := 0
	if avail {
		availInt = 1
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO catalog_items (name, description, price, category, available, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		body.Name, desc, body.Price, cat, availInt, now, now,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "insert catalog item failed: "+err.Error())
		return
	}
	id, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new catalog item id")
		return
	}
	writeJSON(w, http.StatusCreated, catalogItemResponse{
		ID:          id,
		Name:        body.Name,
		Description: &desc,
		Price:       fmt.Sprintf("%.2f", body.Price),
		Category:    &cat,
		Available:   avail,
		CreatedAt:   now,
		UpdatedAt:   now,
	})
}

func (d Deps) handleGetCatalogItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var c catalogItemResponse
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, price, created_at, updated_at
		   FROM catalog_items WHERE id = ?`, id,
	).Scan(&c.ID, &c.Name, &c.Description, &c.Price, &c.CreatedAt, &c.UpdatedAt)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "catalog item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch catalog item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, c)
}

// --------------------------------------------------------------------------- //
//  Order CRUD
// --------------------------------------------------------------------------- //

func (d Deps) handleCreateOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO orders (user_id, status, created_at) VALUES (?, 'draft', ?)`,
		user.ID, now,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "create order failed: "+err.Error())
		return
	}
	id, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new order id")
		return
	}
	writeJSON(w, http.StatusCreated, orderResponse{
		ID:        id,
		UserID:    user.ID,
		Status:    "draft",
		CreatedAt: now,
	})
}

func (d Deps) handleListOrders(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback
		   FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC`,
		user.ID,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "list orders failed: "+err.Error())
		return
	}
	defer rows.Close()
	out := []orderResponse{}
	for rows.Next() {
		var o orderResponse
		if err := rows.Scan(&o.ID, &o.UserID, &o.Status, &o.CreatedAt, &o.SubmittedAt, &o.WaitMinutes, &o.Feedback); err != nil {
			writeError(w, http.StatusInternalServerError, "scan order failed: "+err.Error())
			return
		}
		out = append(out, o)
	}
	if err := rows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (d Deps) handleGetOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	var o orderDetailResponse
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback
		   FROM orders WHERE id = ?`, id,
	).Scan(&o.ID, &o.UserID, &o.Status, &o.CreatedAt, &o.SubmittedAt, &o.WaitMinutes, &o.Feedback)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch order failed: "+err.Error())
		return
	}
	if o.UserID != user.ID {
		writeError(w, http.StatusNotFound, "order not found")
		return
	}

	// Fetch lines
	lineRows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, order_id, catalog_item_id, quantity, unit_price
		   FROM order_lines WHERE order_id = ?`, id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "fetch order lines failed: "+err.Error())
		return
	}
	defer lineRows.Close()
	o.Lines = []orderLineResponse{}
	for lineRows.Next() {
		var ln orderLineResponse
		if err := lineRows.Scan(&ln.ID, &ln.OrderID, &ln.CatalogItemID, &ln.Quantity, &ln.UnitPrice); err != nil {
			writeError(w, http.StatusInternalServerError, "scan order line failed: "+err.Error())
			return
		}
		o.Lines = append(o.Lines, ln)
	}
	if err := lineRows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}

	// Fetch address (optional, one-to-one)
	var addr orderAddressResponse
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, order_id, street, city, zip_code,
		        COALESCE(phone, ''), COALESCE(notes, '')
		   FROM order_addresses WHERE order_id = ?`, id,
	).Scan(&addr.ID, &addr.OrderID, &addr.Street, &addr.City, &addr.ZipCode, &addr.Phone, &addr.Notes)
	if err == nil {
		o.Address = &addr
	} else if !errors.Is(err, sql.ErrNoRows) {
		writeError(w, http.StatusInternalServerError, "fetch order address failed: "+err.Error())
		return
	}

	writeJSON(w, http.StatusOK, o)
}

// --------------------------------------------------------------------------- //
//  Order lines
// --------------------------------------------------------------------------- //

func (d Deps) handleAddOrderLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	order, err := d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	// Look up catalog item to get default price
	var catPrice string
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT price FROM catalog_items WHERE id = ?`, body.CatalogItemID,
	).Scan(&catPrice)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "catalog item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch catalog item failed: "+err.Error())
		return
	}

	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO order_lines (order_id, catalog_item_id, quantity, unit_price)
		 VALUES (?, ?, ?, ?)`,
		orderID, body.CatalogItemID, body.Quantity, catPrice,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "insert order line failed: "+err.Error())
		return
	}
	lineID, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new line id")
		return
	}
	writeJSON(w, http.StatusCreated, orderLineResponse{
		ID:            lineID,
		OrderID:       orderID,
		CatalogItemID: body.CatalogItemID,
		Quantity:      body.Quantity,
		UnitPrice:     catPrice,
	})
}

func (d Deps) handleDeleteOrderLine(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := strconv.ParseInt(r.PathValue("order_id"), 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, "order_id must be an integer")
		return
	}
	lineID, err := strconv.ParseInt(r.PathValue("line_id"), 10, 64)
	if err != nil {
		writeError(w, http.StatusBadRequest, "line_id must be an integer")
		return
	}

	order, err := d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	// Verify line belongs to this order
	var existingOrderID int64
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT order_id FROM order_lines WHERE id = ?`, lineID,
	).Scan(&existingOrderID)
	if err != nil || existingOrderID != orderID {
		writeError(w, http.StatusNotFound, "order line not found")
		return
	}

	if _, err := d.DB.ExecContext(r.Context(),
		`DELETE FROM order_lines WHERE id = ?`, lineID,
	); err != nil {
		writeError(w, http.StatusInternalServerError, "delete order line failed: "+err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// --------------------------------------------------------------------------- //
//  Order address
// --------------------------------------------------------------------------- //

func (d Deps) handleUpsertOrderAddress(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	_, err = d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	phone := ""
	if body.Phone != nil {
		phone = *body.Phone
	}
	notes := ""
	if body.Notes != nil {
		notes = *body.Notes
	}

	// Try update first, then insert
	res, err := d.DB.ExecContext(r.Context(),
		`UPDATE order_addresses SET street = ?, city = ?, zip_code = ?, phone = ?, notes = ?
		   WHERE order_id = ?`,
		strings.TrimSpace(body.Street), strings.TrimSpace(body.City),
		strings.TrimSpace(body.ZipCode), strings.TrimSpace(phone),
		strings.TrimSpace(notes), orderID,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "upsert address failed: "+err.Error())
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		if _, err := d.DB.ExecContext(r.Context(),
			`INSERT INTO order_addresses (order_id, street, city, zip_code, phone, notes)
			 VALUES (?, ?, ?, ?, ?, ?)`,
			orderID, strings.TrimSpace(body.Street), strings.TrimSpace(body.City),
			strings.TrimSpace(body.ZipCode), strings.TrimSpace(phone),
			strings.TrimSpace(notes),
		); err != nil {
			writeError(w, http.StatusInternalServerError, "insert address failed: "+err.Error())
			return
		}
	}

	// Refetch to return the current state
	var addr orderAddressResponse
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, order_id, street, city, zip_code,
		        COALESCE(phone, ''), COALESCE(notes, '')
		   FROM order_addresses WHERE order_id = ?`, orderID,
	).Scan(&addr.ID, &addr.OrderID, &addr.Street, &addr.City, &addr.ZipCode, &addr.Phone, &addr.Notes)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "refetch address failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, addr)
}

// --------------------------------------------------------------------------- //
//  Status transitions (submit / approve / reject)
// --------------------------------------------------------------------------- //

func (d Deps) handleSubmitOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	order, err := d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	// Must have at least one line
	var lineCount int
	if err := d.DB.QueryRowContext(r.Context(),
		`SELECT COUNT(*) FROM order_lines WHERE order_id = ?`, orderID,
	).Scan(&lineCount); err != nil {
		writeError(w, http.StatusInternalServerError, "count lines failed: "+err.Error())
		return
	}
	if lineCount == 0 {
		writeError(w, http.StatusBadRequest, "cannot submit an order with no lines")
		return
	}

	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	if _, err := d.DB.ExecContext(r.Context(),
		`UPDATE orders SET status = 'pending', submitted_at = ? WHERE id = ?`,
		now, orderID,
	); err != nil {
		writeError(w, http.StatusInternalServerError, "submit order failed: "+err.Error())
		return
	}

	d.writeOrderDetail(w, r, orderID)
}

func (d Deps) handleApproveOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	order, err := d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	if _, err := d.DB.ExecContext(r.Context(),
		`UPDATE orders SET status = 'approved', wait_minutes = ?, feedback = ? WHERE id = ?`,
		body.WaitMinutes, body.Feedback, orderID,
	); err != nil {
		writeError(w, http.StatusInternalServerError, "approve order failed: "+err.Error())
		return
	}

	d.writeOrderDetail(w, r, orderID)
}

func (d Deps) handleRejectOrder(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	orderID, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	order, err := d.fetchOrderForUser(r, orderID, user.ID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
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

	if _, err := d.DB.ExecContext(r.Context(),
		`UPDATE orders SET status = 'rejected', feedback = ? WHERE id = ?`,
		body.Feedback, orderID,
	); err != nil {
		writeError(w, http.StatusInternalServerError, "reject order failed: "+err.Error())
		return
	}

	d.writeOrderDetail(w, r, orderID)
}

// --------------------------------------------------------------------------- //
//  Helpers
// --------------------------------------------------------------------------- //

// fetchOrderForUser fetches an order by id and verifies it belongs to
// the given user. Returns sql.ErrNoRows when not found or not owned.
func (d Deps) fetchOrderForUser(r *http.Request, orderID, userID int64) (orderResponse, error) {
	var o orderResponse
	err := d.DB.QueryRowContext(r.Context(),
		`SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback
		   FROM orders WHERE id = ?`, orderID,
	).Scan(&o.ID, &o.UserID, &o.Status, &o.CreatedAt, &o.SubmittedAt, &o.WaitMinutes, &o.Feedback)
	if err != nil {
		return o, err
	}
	if o.UserID != userID {
		return o, sql.ErrNoRows
	}
	return o, nil
}

// writeOrderDetail fetches the full order detail (with lines + address)
// and writes it as JSON. Used by submit/approve/reject to return the
// updated state.
func (d Deps) writeOrderDetail(w http.ResponseWriter, r *http.Request, orderID int64) {
	var o orderDetailResponse
	err := d.DB.QueryRowContext(r.Context(),
		`SELECT id, user_id, status, created_at, submitted_at, wait_minutes, feedback
		   FROM orders WHERE id = ?`, orderID,
	).Scan(&o.ID, &o.UserID, &o.Status, &o.CreatedAt, &o.SubmittedAt, &o.WaitMinutes, &o.Feedback)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "refetch order failed: "+err.Error())
		return
	}

	lineRows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, order_id, catalog_item_id, quantity, unit_price
		   FROM order_lines WHERE order_id = ?`, orderID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "fetch order lines failed: "+err.Error())
		return
	}
	defer lineRows.Close()
	o.Lines = []orderLineResponse{}
	for lineRows.Next() {
		var ln orderLineResponse
		if err := lineRows.Scan(&ln.ID, &ln.OrderID, &ln.CatalogItemID, &ln.Quantity, &ln.UnitPrice); err != nil {
			writeError(w, http.StatusInternalServerError, "scan order line failed: "+err.Error())
			return
		}
		o.Lines = append(o.Lines, ln)
	}
	if err := lineRows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}

	var addr orderAddressResponse
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, order_id, street, city, zip_code,
		        COALESCE(phone, ''), COALESCE(notes, '')
		   FROM order_addresses WHERE order_id = ?`, orderID,
	).Scan(&addr.ID, &addr.OrderID, &addr.Street, &addr.City, &addr.ZipCode, &addr.Phone, &addr.Notes)
	if err == nil {
		o.Address = &addr
	} else if !errors.Is(err, sql.ErrNoRows) {
		writeError(w, http.StatusInternalServerError, "fetch order address failed: "+err.Error())
		return
	}

	writeJSON(w, http.StatusOK, o)
}
