// HTTP helpers reused by every resource's routes.go. Keeping them in
// the shared package means resource handlers stay terse and uniform
// across the codebase — no duplicate writeJSON/decodeJSON/pathID
// implementations.
package shared

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
)

// WriteJSON serialises body as JSON and writes status to w. Sets
// Content-Type on the way out.
func WriteJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

// WriteError writes a {detail, status} error envelope matching the
// wrapper-shared contract every dev_skel backend honours.
func WriteError(w http.ResponseWriter, status int, detail string) {
	WriteJSON(w, status, map[string]any{
		"detail": detail,
		"status": status,
	})
}

// DecodeJSON decodes the request body into dst with unknown-field
// rejection (so callers catch typos in payloads early).
func DecodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dst)
}

// PathID parses a uint id from r.PathValue(name).
func PathID(r *http.Request, name string) (uint, error) {
	raw := r.PathValue(name)
	id, err := strconv.ParseUint(raw, 10, 64)
	if err != nil {
		return 0, errors.New("path " + name + " must be an integer")
	}
	return uint(id), nil
}

// IsUniqueViolation matches the SQLite + Postgres unique-constraint
// error strings without depending on driver-specific error types.
// Resource adapters call this to translate raw GORM errors into
// shared.ErrConflict before returning to services.
func IsUniqueViolation(err error) bool {
	if err == nil {
		return false
	}
	msg := err.Error()
	return strings.Contains(msg, "UNIQUE constraint failed") ||
		strings.Contains(msg, "duplicate key value") ||
		strings.Contains(msg, "violates unique constraint")
}
