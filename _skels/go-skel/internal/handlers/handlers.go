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
//
// Routes are registered in main.go via Register; this package keeps
// the per-resource logic isolated and uses Go 1.22's method-aware
// http.ServeMux for routing (no third-party router required).
package handlers

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/example/go-skel/internal/auth"
	"github.com/example/go-skel/internal/config"
)

// Deps bundles every collaborator the handlers need so main.go can
// wire them once and pass a single value into Register.
type Deps struct {
	Cfg config.Config
	DB  *sql.DB
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

	var existing int64
	err := d.DB.QueryRowContext(r.Context(),
		`SELECT id FROM users WHERE username = ?`, body.Username,
	).Scan(&existing)
	if err == nil {
		writeError(w, http.StatusConflict, "user '"+body.Username+"' already exists")
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeError(w, http.StatusInternalServerError, "database error: "+err.Error())
		return
	}

	hashed, err := auth.HashPassword(body.Password)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "password hash failed: "+err.Error())
		return
	}
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)`,
		body.Username, body.Email, hashed,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "insert user failed: "+err.Error())
		return
	}
	newID, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new user id")
		return
	}

	access, err := auth.MintAccessToken(d.Cfg, newID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint access token failed: "+err.Error())
		return
	}
	refresh, err := auth.MintRefreshToken(d.Cfg, newID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint refresh token failed: "+err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{
		"user":    map[string]any{"id": newID, "username": body.Username, "email": body.Email},
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

	var (
		id           int64
		username     string
		passwordHash string
	)
	query := `SELECT id, username, password_hash FROM users WHERE username = ?`
	if strings.Contains(body.Username, "@") {
		query = `SELECT id, username, password_hash FROM users WHERE email = ?`
	}
	err := d.DB.QueryRowContext(r.Context(),
		query,
		body.Username,
	).Scan(&id, &username, &passwordHash)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}
	if !auth.VerifyPassword(body.Password, passwordHash) {
		writeError(w, http.StatusUnauthorized, "invalid username or password")
		return
	}

	access, err := auth.MintAccessToken(d.Cfg, id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint access token failed: "+err.Error())
		return
	}
	refresh, err := auth.MintRefreshToken(d.Cfg, id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "mint refresh token failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"access":   access,
		"refresh":  refresh,
		"user_id":  id,
		"username": username,
	})
}

// --------------------------------------------------------------------------- //
//  /api/categories/*
// --------------------------------------------------------------------------- //

type categoryRow struct {
	ID          int64   `json:"id"`
	Name        string  `json:"name"`
	Description *string `json:"description"`
	CreatedAt   string  `json:"created_at"`
	UpdatedAt   string  `json:"updated_at"`
}

type createCategoryPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
}

func (d Deps) handleListCategories(w http.ResponseWriter, r *http.Request) {
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM categories ORDER BY id`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "list categories failed: "+err.Error())
		return
	}
	defer rows.Close()
	out := []categoryRow{}
	for rows.Next() {
		var c categoryRow
		if err := rows.Scan(&c.ID, &c.Name, &c.Description, &c.CreatedAt, &c.UpdatedAt); err != nil {
			writeError(w, http.StatusInternalServerError, "scan category failed: "+err.Error())
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

func (d Deps) handleCreateCategory(w http.ResponseWriter, r *http.Request) {
	var body createCategoryPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "category name cannot be empty")
		return
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO categories (name, description, created_at, updated_at)
		 VALUES (?, ?, ?, ?)`,
		body.Name, body.Description, now, now,
	)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE constraint failed") {
			writeError(w, http.StatusConflict, "category with name '"+body.Name+"' already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, "insert category failed: "+err.Error())
		return
	}
	id, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new category id")
		return
	}
	writeJSON(w, http.StatusCreated, categoryRow{
		ID:          id,
		Name:        body.Name,
		Description: body.Description,
		CreatedAt:   now,
		UpdatedAt:   now,
	})
}

func (d Deps) handleGetCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var c categoryRow
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM categories WHERE id = ?`, id,
	).Scan(&c.ID, &c.Name, &c.Description, &c.CreatedAt, &c.UpdatedAt)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "category not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch category failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, c)
}

func (d Deps) handleUpdateCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	var body createCategoryPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "category name cannot be empty")
		return
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`UPDATE categories SET name = ?, description = ?, updated_at = ?
		   WHERE id = ?`,
		body.Name, body.Description, now, id,
	)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE constraint failed") {
			writeError(w, http.StatusConflict, "category with name '"+body.Name+"' already exists")
			return
		}
		writeError(w, http.StatusInternalServerError, "update category failed: "+err.Error())
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		writeError(w, http.StatusNotFound, "category not found")
		return
	}
	var c categoryRow
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM categories WHERE id = ?`, id,
	).Scan(&c.ID, &c.Name, &c.Description, &c.CreatedAt, &c.UpdatedAt)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "refetch category failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, c)
}

func (d Deps) handleDeleteCategory(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	res, err := d.DB.ExecContext(r.Context(),
		`DELETE FROM categories WHERE id = ?`, id,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "delete category failed: "+err.Error())
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		writeError(w, http.StatusNotFound, "category not found")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// --------------------------------------------------------------------------- //
//  /api/items/*
// --------------------------------------------------------------------------- //

type itemRow struct {
	ID          int64   `json:"id"`
	Name        string  `json:"name"`
	Description *string `json:"description"`
	IsCompleted bool    `json:"is_completed"`
	CategoryID  *int64  `json:"category_id"`
	CreatedAt   string  `json:"created_at"`
	UpdatedAt   string  `json:"updated_at"`
}

type createItemPayload struct {
	Name        string  `json:"name"`
	Description *string `json:"description"`
	IsCompleted bool    `json:"is_completed"`
	CategoryID  *int64  `json:"category_id"`
}

func (d Deps) handleListItems(w http.ResponseWriter, r *http.Request) {
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, name, description, is_completed, category_id, created_at, updated_at
		   FROM items ORDER BY created_at DESC, id DESC`)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "list items failed: "+err.Error())
		return
	}
	defer rows.Close()
	out := []itemRow{}
	for rows.Next() {
		var it itemRow
		var completed int
		if err := rows.Scan(&it.ID, &it.Name, &it.Description, &completed, &it.CategoryID, &it.CreatedAt, &it.UpdatedAt); err != nil {
			writeError(w, http.StatusInternalServerError, "scan item failed: "+err.Error())
			return
		}
		it.IsCompleted = completed != 0
		out = append(out, it)
	}
	if err := rows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (d Deps) handleCreateItem(w http.ResponseWriter, r *http.Request) {
	var body createItemPayload
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		writeError(w, http.StatusBadRequest, "item name cannot be empty")
		return
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	completedInt := 0
	if body.IsCompleted {
		completedInt = 1
	}
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO items (name, description, is_completed, category_id, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		body.Name, body.Description, completedInt, body.CategoryID, now, now,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "insert item failed: "+err.Error())
		return
	}
	id, err := res.LastInsertId()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not read new item id")
		return
	}
	writeJSON(w, http.StatusCreated, itemRow{
		ID:          id,
		Name:        body.Name,
		Description: body.Description,
		IsCompleted: body.IsCompleted,
		CategoryID:  body.CategoryID,
		CreatedAt:   now,
		UpdatedAt:   now,
	})
}

func (d Deps) handleGetItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	it, err := d.fetchItem(r, id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, http.StatusNotFound, "item not found")
			return
		}
		writeError(w, http.StatusInternalServerError, "fetch item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, it)
}

func (d Deps) handleCompleteItem(w http.ResponseWriter, r *http.Request) {
	id, err := pathID(r)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`UPDATE items SET is_completed = 1, updated_at = ? WHERE id = ?`,
		now, id,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "complete item failed: "+err.Error())
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		writeError(w, http.StatusNotFound, "item not found")
		return
	}
	it, err := d.fetchItem(r, id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "refetch item failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, it)
}

func (d Deps) fetchItem(r *http.Request, id int64) (itemRow, error) {
	var it itemRow
	var completed int
	err := d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, is_completed, category_id, created_at, updated_at
		   FROM items WHERE id = ?`, id,
	).Scan(&it.ID, &it.Name, &it.Description, &completed, &it.CategoryID, &it.CreatedAt, &it.UpdatedAt)
	if err != nil {
		return it, err
	}
	it.IsCompleted = completed != 0
	return it, nil
}

// --------------------------------------------------------------------------- //
//  /api/state/*
// --------------------------------------------------------------------------- //

type upsertStatePayload struct {
	Value string `json:"value"`
}

func (d Deps) handleListState(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.UserFromContext(r.Context())
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT state_key, state_value FROM react_state WHERE user_id = ? ORDER BY state_key`,
		user.ID,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "list state failed: "+err.Error())
		return
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			writeError(w, http.StatusInternalServerError, "scan state failed: "+err.Error())
			return
		}
		out[k] = v
	}
	if err := rows.Err(); err != nil {
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
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
	// UPDATE first; if the row does not exist, INSERT. We avoid
	// dialect-specific upsert syntax (`ON CONFLICT` for SQLite,
	// `ON DUPLICATE KEY UPDATE` for MySQL, MERGE for SQL Server, ...)
	// by branching on the row count.
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`UPDATE react_state SET state_value = ?, updated_at = ?
		   WHERE user_id = ? AND state_key = ?`,
		body.Value, now, user.ID, key,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "upsert state failed: "+err.Error())
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		if _, err := d.DB.ExecContext(r.Context(),
			`INSERT INTO react_state (user_id, state_key, state_value, updated_at)
			 VALUES (?, ?, ?, ?)`,
			user.ID, key, body.Value, now,
		); err != nil {
			writeError(w, http.StatusInternalServerError, "insert state failed: "+err.Error())
			return
		}
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
	if _, err := d.DB.ExecContext(r.Context(),
		`DELETE FROM react_state WHERE user_id = ? AND state_key = ?`,
		user.ID, key,
	); err != nil {
		writeError(w, http.StatusInternalServerError, "delete state failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{})
}

// --------------------------------------------------------------------------- //
//  Helpers
// --------------------------------------------------------------------------- //

func pathID(r *http.Request) (int64, error) {
	raw := r.PathValue("id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0, errors.New("path id must be an integer")
	}
	return id, nil
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
		// Allow callers to lenient-decode by retrying without
		// DisallowUnknownFields if they want — for now we just
		// surface the error; the React client never sends extra
		// fields anyway.
		return err
	}
	return nil
}
