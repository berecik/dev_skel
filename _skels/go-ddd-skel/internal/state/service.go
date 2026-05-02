// Service-layer logic for /api/state.
package state

import (
	"context"
	"errors"
	"fmt"

	"github.com/example/go-ddd-skel/internal/shared"
)

// Service coordinates state.Repository for HTTP routes.
type Service struct {
	repo Repository
}

// NewService builds a state Service.
func NewService(repo Repository) *Service {
	return &Service{repo: repo}
}

// Map returns every key/value pair owned by userID as a flat map.
func (s *Service) Map(ctx context.Context, userID uint) (map[string]string, error) {
	rows, err := s.repo.ListForUser(ctx, userID)
	if err != nil {
		return nil, err
	}
	out := make(map[string]string, len(rows))
	for _, row := range rows {
		out[row.StateKey] = row.StateValue
	}
	return out, nil
}

// Upsert stores value under key for userID, inserting or updating as
// needed.
func (s *Service) Upsert(ctx context.Context, userID uint, key, value string) error {
	if key == "" {
		return fmt.Errorf("%w: state key cannot be empty", shared.ErrValidation)
	}
	row, err := s.repo.GetForUser(ctx, userID, key)
	switch {
	case err == nil:
		row.StateValue = value
		return s.repo.Save(ctx, &row)
	case errors.Is(err, shared.ErrNotFound):
		row = ReactState{
			UserID:     userID,
			StateKey:   key,
			StateValue: value,
		}
		return s.repo.Save(ctx, &row)
	default:
		return err
	}
}

// Delete removes the key for userID. No-ops when the key is absent
// (matches the wrapper-shared 200-with-empty-body contract).
func (s *Service) Delete(ctx context.Context, userID uint, key string) error {
	if key == "" {
		return fmt.Errorf("%w: state key cannot be empty", shared.ErrValidation)
	}
	return s.repo.DeleteForUser(ctx, userID, key)
}
