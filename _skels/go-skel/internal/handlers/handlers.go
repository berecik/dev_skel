// Package handlers implements the wrapper-shared HTTP contract every
// dev_skel backend honours so the React frontend's typed fetch
// client + JWT auth flow works against this Go service unchanged:
//
//   - GET  /                          → project info
//   - GET  /health                    → health check
//   - POST /api/auth/register         → 201 {user, access, refresh}
//   - POST /api/auth/login            → 200 {access, refresh, user_id, username}
//   - GET/POST      /api/categories   → JWT-protected CRUD
//   - GET/PUT/DELETE /api/categories/{id}
//   - GET/POST  /api/items            → JWT-protected CRUD
//   - GET  /api/items/{id}            → JWT-protected
//   - POST /api/items/{id}/complete   → JWT-protected idempotent flip
//   - GET/PUT/DELETE  /api/state[/{key}] → per-user JSON KV store
//   - GET/POST        /api/catalog[/{id}]  → JWT-protected catalog CRUD
//   - POST/GET        /api/orders          → JWT-protected order CRUD
//   - GET             /api/orders/{id}     → order detail with lines + address
//   - POST/DELETE     /api/orders/{id}/lines[/{line_id}] → order lines
//   - PUT             /api/orders/{id}/address → delivery address
//   - POST            /api/orders/{id}/submit  → draft → submitted
//   - POST            /api/orders/{id}/approve → submitted → approved
//   - POST            /api/orders/{id}/reject  → submitted → rejected
//
// Every database access goes through GORM (`gorm.io/gorm`) — no raw
// SQL anywhere in the handler layer. Datetime columns are
// `time.Time` so they serialise as RFC3339 in responses and the
// generic `created_at` / `updated_at` ORM hooks fire on writes.
package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"gorm.io/gorm"

	"github.com/example/go-skel/internal/auth"
	"github.com/example/go-skel/internal/config"
	"github.com/example/go-skel/internal/models"
)

// Deps bundles every collaborator the handlers need so main.go can
// wire them once and pass a single value into Register.
type Deps struct {
	Cfg config.Config
	DB  *gorm.DB
}

// Register attaches every wrapper-shared route to mux. The JWT
// middleware fronts /api/categories, /api/items, and /api/state;
// /api/auth/* and the root routes are intentionally unauthenticated.
func Register(mux *http.ServeMux, d Deps) {
	mux.Handle("GET /", http.HandlerFunc(d.handleIndex))
	mux.Handle("GET /health", http.HandlerFunc(d.handleHealth))

	mux.Handle("POST /api/auth/register", http.HandlerFunc(d.handleRegister))
	mux.Handle("POST /api/auth/login", http.HandlerFunc(d.handleLogin))

	jwt := auth.Middleware(d.Cfg, d.DB)
	mux.Handle("GET /api/categories", jwt(http.HandlerFunc(d.handleListCategories)))
	mux.Handle("POST /api/categories", jwt(http.HandlerFunc(d.handleCreateCategory)))
	mux.Handle("GET /api/categories/{id}", jwt(http.HandlerFunc(d.handleGetCategory)))
	mux.Handle("PUT /api/categories/{id}", jwt(http.HandlerFunc(d.handleUpdateCategory)))
	mux.Handle("DELETE /api/categories/{id}", jwt(http.HandlerFunc(d.handleDeleteCategory)))

	mux.Handle("GET /api/items", jwt(http.HandlerFunc(d.handleListItems)))
	mux.Handle("POST /api/items", jwt(http.HandlerFunc(d.handleCreateItem)))
	mux.Handle("GET /api/items/{id}", jwt(http.HandlerFunc(d.handleGetItem)))
	mux.Handle("POST /api/items/{id}/complete", jwt(http.HandlerFunc(d.handleCompleteItem)))

	mux.Handle("GET /api/state", jwt(http.HandlerFunc(d.handleListState)))
	mux.Handle("PUT /api/state/{key}", jwt(http.HandlerFunc(d.handleUpsertState)))
	mux.Handle("DELETE /api/state/{key}", jwt(http.HandlerFunc(d.handleDeleteState)))

	mux.Handle("GET /api/catalog", jwt(http.HandlerFunc(d.handleListCatalog)))
	mux.Handle("POST /api/catalog", jwt(http.HandlerFunc(d.handleCreateCatalogItem)))
	mux.Handle("GET /api/catalog/{id}", jwt(http.HandlerFunc(d.handleGetCatalogItem)))

	mux.Handle("POST /api/orders", jwt(http.HandlerFunc(d.handleCreateOrder)))
	mux.Handle("GET /api/orders", jwt(http.HandlerFunc(d.handleListOrders)))
	mux.Handle("GET /api/orders/{id}", jwt(http.HandlerFunc(d.handleGetOrder)))
	mux.Handle("POST /api/orders/{id}/lines", jwt(http.HandlerFunc(d.handleAddOrderLine)))
	mux.Handle("DELETE /api/orders/{order_id}/lines/{line_id}", jwt(http.HandlerFunc(d.handleDeleteOrderLine)))
	mux.Handle("PUT /api/orders/{id}/address", jwt(http.HandlerFunc(d.handleUpsertOrderAddress)))
	mux.Handle("POST /api/orders/{id}/submit", jwt(http.HandlerFunc(d.handleSubmitOrder)))
	mux.Handle("POST /api/orders/{id}/approve", jwt(http.HandlerFunc(d.handleApproveOrder)))
	mux.Handle("POST /api/orders/{id}/reject", jwt(http.HandlerFunc(d.handleRejectOrder)))
}

// --------------------------------------------------------------------------- //
//  Root
// --------------------------------------------------------------------------- //

func (d Deps) handleIndex(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"project":   "go-skel",
		"version":   "1.0.0",
		"framework": "net/http",
		"status":    "running",
	})
}

func (d Deps) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"status": "healthy"})
}

// --------------------------------------------------------------------------- //
//  /api/auth/*
// --------------------------------------------------------------------------- //

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

func (d Deps) handleRegister(w http.ResponseWriter, r *http.Request) {
	var body registerPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Username) == "" {
		writeError(w, http.StatusBadRequest, "username cannot be empty")
		return
	}
	if len(body.Password) < 6 {
		writeError(w, http.StatusBadRequest, "password must be at least 6 characters")
		return
	}
	if body.PasswordConfirm != "" && body.PasswordConfirm != body.Password {
		writeError(w, http.StatusBadRequest, "password and password_confirm do not match")
		return
	}

	tx := d.DB.WithContext(r.Context())
	var existing models.User
	err := tx.Where("username = ?", body.Username).First(&existing).Error
	if err == nil {
		writeError(w, http.StatusConflict, "user '"+body.Username+"' already exists")
		return
	}
	if !errors.Is(err, gorm.ErrRecordNotFound) {
		writeError(w, http.StatusInternalServerError, "database error: "+err.Error())
		return
	}

	hashed, err := auth.HashPassword(body.Password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "password hash failed: "+err.Error())
		return
	}
	user := models.User{
		Username:     body.Username,
		Email:        body.Email,
		PasswordHash: hashed,
	}
	if err := tx.Create(&user).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "insert user failed: "+err.Error())
		return
	}

	access, err := auth.MintAccessToken(d.Cfg, int64(user.ID))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint access token failed: "+err.Error())
		return
	}
	refresh, err := auth.MintRefreshToken(d.Cfg, int64(user.ID))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint refresh token failed: "+err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{
		"user":    map[string]any{"id": user.ID, "username": user.Username, "email": user.Email},
		"access":  access,
		"refresh": refresh,
	})
}

func (d Deps) handleLogin(w http.ResponseWriter, r *http.Request) {
	var body loginPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}
	if body.Username == "" || body.Password == "" {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}

	column := "username"
	if strings.Contains(body.Username, "@") {
		column = "email"
	}
	var user models.User
	err := d.DB.WithContext(r.Context()).
		Where(column+" = ?", body.Username).
		First(&user).Error
	if err != nil {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}
	if !auth.VerifyPassword(body.Password, user.PasswordHash) {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}

	access, err := auth.MintAccessToken(d.Cfg, int64(user.ID))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint access token failed: "+err.Error())
		return
	}
	refresh, err := auth.MintRefreshToken(d.Cfg, int64(user.ID))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint refresh token failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"access":   access,
		"refresh":  refresh,
		"user_id":  user.ID,
		"username": user.Username,
	})
}

// --------------------------------------------------------------------------- //
//  /api/categories/*
// --------------------------------------------------------------------------- //

type categoryPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
}

func (d Deps) handleListCategories(w http.ResponseWriter, r *http.Request) {
	var rows []models.Category
	if err := d.DB.WithContext(r.Context()).
		Order("id").Find(&rows).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "list categories failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []models.Category{}
	}
	writeJSON(w, http.StatusOK, rows)
}

func (d Deps) handleCreateCategory(w http.ResponseWriter, r *http.Request) {
	var body categoryPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "category name cannot be empty")
		return
	}
	cat := models.Category{Name: body.Name}
	if body.Description != nil {
		cat.Description = *body.Description
	}
	if err := d.DB.WithContext(r.Context()).Create(&cat).Error; err != nil {
		if isUniqueViolation(err) {
			writeError(w, http.StatusConflict,
				"category with name '"+body.Name+"' already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, "insert category failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, cat)
}

func (d Deps) handleGetCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var cat models.Category
	if err := d.DB.WithContext(r.Context()).First(&cat, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "category not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch category failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, cat)
}

func (d Deps) handleUpdateCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body categoryPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "category name cannot be empty")
		return
	}
	tx := d.DB.WithContext(r.Context())
	var cat models.Category
	if err := tx.First(&cat, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "category not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch category failed: "+err.Error())
		return
	}
	cat.Name = body.Name
	if body.Description != nil {
		cat.Description = *body.Description
	} else {
		cat.Description = ""
	}
	if err := tx.Save(&cat).Error; err != nil {
		if isUniqueViolation(err) {
			writeError(w, http.StatusConflict,
				"category with name '"+body.Name+"' already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, "update category failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, cat)
}

func (d Deps) handleDeleteCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	// Load the row first so the `Category.BeforeDelete` hook (which
	// nulls dependent items.category_id values) sees a fully-populated
	// struct. Calling `tx.Delete(&Category{}, id)` runs the hook with
	// only the FK as the WHERE clause and a zero-value receiver, so
	// the hook's reference to `c.ID` would be wrong.
	tx := d.DB.WithContext(r.Context())
	var cat models.Category
	if err := tx.First(&cat, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "category not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch category failed: "+err.Error())
		return
	}
	if err := tx.Delete(&cat).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "delete category failed: "+err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// --------------------------------------------------------------------------- //
//  /api/items/*
// --------------------------------------------------------------------------- //

type itemPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
	IsCompleted bool    `json:"is_completed"`
	CategoryID  *uint   `json:"category_id"`
}

func (d Deps) handleListItems(w http.ResponseWriter, r *http.Request) {
	var rows []models.Item
	if err := d.DB.WithContext(r.Context()).
		Order("created_at DESC, id DESC").Find(&rows).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "list items failed: "+err.Error())
		return
	}
	if rows == nil {
		rows = []models.Item{}
	}
	writeJSON(w, http.StatusOK, rows)
}

func (d Deps) handleCreateItem(w http.ResponseWriter, r *http.Request) {
	var body itemPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "item name cannot be empty")
		return
	}
	item := models.Item{
		Name:        body.Name,
		IsCompleted: body.IsCompleted,
		CategoryID:  body.CategoryID,
	}
	if body.Description != nil {
		item.Description = *body.Description
	}
	if err := d.DB.WithContext(r.Context()).Create(&item).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "insert item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, item)
}

func (d Deps) handleGetItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var item models.Item
	if err := d.DB.WithContext(r.Context()).First(&item, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (d Deps) handleCompleteItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r, "id")
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	tx := d.DB.WithContext(r.Context())
	var item models.Item
	if err := tx.First(&item, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			writeError(w, http.StatusNotFound, "item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch item failed: "+err.Error())
		return
	}
	item.IsCompleted = true
	if err := tx.Save(&item).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "complete item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

// --------------------------------------------------------------------------- //
//  /api/state/*
// --------------------------------------------------------------------------- //

type upsertStatePayload struct {
	Value string `json:"value"`
}

func (d Deps) handleListState(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	var rows []models.ReactState
	if err := d.DB.WithContext(r.Context()).
		Where("user_id = ?", user.ID).
		Order("state_key").
		Find(&rows).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "list state failed: "+err.Error())
		return
	}
	out := make(map[string]string, len(rows))
	for _, row := range rows {
		out[row.StateKey] = row.StateValue
	}
	writeJSON(w, http.StatusOK, out)
}

func (d Deps) handleUpsertState(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	key := r.PathValue("key")
	if key == "" {
		writeError(w, http.StatusBadRequest, "state key cannot be empty")
		return
	}
	var body upsertStatePayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	tx := d.DB.WithContext(r.Context())
	var row models.ReactState
	err := tx.Where("user_id = ? AND state_key = ?", user.ID, key).First(&row).Error
	switch {
	case err == nil:
		row.StateValue = body.Value
		if err := tx.Save(&row).Error; err != nil {
			writeError(w, http.StatusInternalServerError, "upsert state failed: "+err.Error())
			return
		}
	case errors.Is(err, gorm.ErrRecordNotFound):
		row = models.ReactState{
			UserID:     uint(user.ID),
			StateKey:   key,
			StateValue: body.Value,
		}
		if err := tx.Create(&row).Error; err != nil {
			writeError(w, http.StatusInternalServerError, "insert state failed: "+err.Error())
			return
		}
	default:
		writeError(w, http.StatusInternalServerError, "fetch state failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"key": key})
}

func (d Deps) handleDeleteState(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	key := r.PathValue("key")
	if key == "" {
		writeError(w, http.StatusBadRequest, "state key cannot be empty")
		return
	}
	if err := d.DB.WithContext(r.Context()).
		Where("user_id = ? AND state_key = ?", user.ID, key).
		Delete(&models.ReactState{}).Error; err != nil {
		writeError(w, http.StatusInternalServerError, "delete state failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{})
}

// --------------------------------------------------------------------------- //
//  Helpers
// --------------------------------------------------------------------------- //

func pathID(r *http.Request, name string) (uint, error) {
	raw := r.PathValue(name)
	id, err := strconv.ParseUint(raw, 10, 64)
	if err != nil {
		return 0, errors.New("path " + name + " must be an integer")
	}
	return uint(id), nil
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeError(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]any{
		"detail": detail,
		"status": status,
	})
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		return err
	}
	return nil
}

// isUniqueViolation matches the SQLite + Postgres unique-constraint
// error strings without depending on driver-specific error types.
func isUniqueViolation(err error) bool {
	if err == nil {
		return false
	}
	msg := err.Error()
	return strings.Contains(msg, "UNIQUE constraint failed") ||
		strings.Contains(msg, "duplicate key value") ||
		strings.Contains(msg, "violates unique constraint")
}
