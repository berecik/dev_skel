// Package main wires the wrapper-shared backend stack and starts the
// HTTP server. The skeleton intentionally uses the standard library
// (net/http with Go 1.22+ method-aware routing) so the only deps are
// the JWT library, bcrypt, and the pure-Go SQLite driver.
//
// Resources are organised as light DDD layers under internal/:
// each resource (items, categories, orders, catalog, state, users)
// owns a Repository interface, an adapter implementing it, a
// Service, depts.go providers, and a routes.go that wires HTTP to
// Service. main.go's job is just to compose them.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/go-ddd-skel/internal/auth"
	"github.com/example/go-ddd-skel/internal/catalog"
	"github.com/example/go-ddd-skel/internal/categories"
	"github.com/example/go-ddd-skel/internal/config"
	"github.com/example/go-ddd-skel/internal/db"
	"github.com/example/go-ddd-skel/internal/items"
	"github.com/example/go-ddd-skel/internal/orders"
	"github.com/example/go-ddd-skel/internal/seed"
	"github.com/example/go-ddd-skel/internal/state"
	usersAdapters "github.com/example/go-ddd-skel/internal/users/adapters"
)

func main() {
	cfg := config.FromEnv()

	conn, err := db.Open(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("open database (%s): %v", cfg.DatabaseURL, err)
	}
	// Close the underlying *sql.DB on exit. GORM holds the
	// connection pool here; calling sqlDB.Close() on a nil result is
	// a no-op so the deferred call is safe even if (somehow) the
	// dialect didn't expose one.
	if sqlDB, dbErr := conn.DB(); dbErr == nil {
		defer sqlDB.Close()
	}

	// Build repositories first so every collaborator that needs them
	// (auth middleware, seed flow, services) sees the same instance.
	userRepo := usersAdapters.NewGormUserRepository(conn)

	if err := seed.SeedDefaultAccounts(context.Background(), userRepo); err != nil {
		log.Fatalf("seed default accounts: %v", err)
	}

	// Wire services via each resource's depts.go provider. depts
	// builds the GORM adapter and hands it to the Service so main
	// stays free of repository details.
	authSvc := auth.NewService(cfg, userRepo)
	itemSvc := items.NewServiceFromDB(conn)
	categorySvc := categories.NewServiceFromDB(conn)
	stateSvc := state.NewServiceFromDB(conn)
	catalogSvc := catalog.NewServiceFromDB(conn)
	orderSvc := orders.NewServiceFromDB(conn)

	// JWT middleware is shared across every protected route.
	jwt := auth.Middleware(cfg, userRepo)

	mux := http.NewServeMux()
	mux.Handle("GET /", http.HandlerFunc(handleIndex))
	mux.Handle("GET /health", http.HandlerFunc(handleHealth))
	auth.RegisterRoutes(mux, authSvc)
	items.RegisterRoutes(mux, itemSvc, jwt)
	categories.RegisterRoutes(mux, categorySvc, jwt)
	state.RegisterRoutes(mux, stateSvc, jwt)
	catalog.RegisterRoutes(mux, catalogSvc, jwt)
	orders.RegisterRoutes(mux, orderSvc, jwt)

	addr := fmt.Sprintf("%s:%d", cfg.ServiceHost, cfg.ServicePort)
	srv := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Graceful shutdown so `Ctrl-C` (or the supervisor's SIGTERM) lets
	// in-flight requests drain instead of being cut mid-write.
	idleClosed := make(chan struct{})
	go func() {
		sigs := make(chan os.Signal, 1)
		signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
		<-sigs
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("shutdown error: %v", err)
		}
		close(idleClosed)
	}()

	log.Printf("go-skel listening on %s (db=%s, issuer=%s)",
		addr, cfg.DatabaseURL, cfg.JWTIssuer)
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("listen: %v", err)
	}
	<-idleClosed
}

func handleIndex(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"project":   "go-skel",
		"version":   "1.0.0",
		"framework": "net/http",
		"status":    "running",
	})
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"status": "healthy"})
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
