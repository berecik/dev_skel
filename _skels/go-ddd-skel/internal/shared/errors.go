// Domain errors. Routes translate these into HTTP status codes via
// the helpers in this file. Keeping them as sentinel values (rather
// than typed structs) lets services wrap them with extra context via
// fmt.Errorf("%w: ...", shared.ErrNotFound) and lets callers compare
// with errors.Is.
package shared

import (
	"errors"
	"net/http"
)

// Sentinel domain errors. Wrap them with fmt.Errorf("%w: ...", err)
// to add context while preserving the kind for callers.
var (
	ErrNotFound     = errors.New("not found")
	ErrConflict     = errors.New("conflict")
	ErrValidation   = errors.New("validation failed")
	ErrUnauthorized = errors.New("unauthorized")
	ErrForbidden    = errors.New("forbidden")
)

// HTTPStatus maps a domain error to its canonical HTTP status code.
// Returns 500 when err is nil or unrecognised — callers should treat
// 500 as the "did not match a domain kind" signal and supply their
// own message.
func HTTPStatus(err error) int {
	switch {
	case err == nil:
		return http.StatusOK
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrConflict):
		return http.StatusConflict
	case errors.Is(err, ErrValidation):
		return http.StatusBadRequest
	case errors.Is(err, ErrUnauthorized):
		return http.StatusUnauthorized
	case errors.Is(err, ErrForbidden):
		return http.StatusForbidden
	default:
		return http.StatusInternalServerError
	}
}
