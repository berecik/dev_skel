// Package main wires the wrapper-shared backend stack and starts the
// HTTP server. The skeleton intentionally uses the standard library
// (net/http with Go 1.22+ method-aware routing) so the only deps are
// the JWT library, bcrypt, and the pure-Go SQLite driver.
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/example/go-skel/internal/config"
	"github.com/example/go-skel/internal/db"
	"github.com/example/go-skel/internal/handlers"
	"github.com/example/go-skel/internal/seed"
)

func main() {
	cfg := config.FromEnv()

	conn, err := db.Open(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("open database (%s): %v", cfg.DatabaseURL, err)
	}
	defer conn.Close()

	if err := seed.SeedDefaultAccounts(context.Background(), conn); err != nil {
		log.Fatalf("seed default accounts: %v", err)
	}

	mux := http.NewServeMux()
	handlers.Register(mux, handlers.Deps{Cfg: cfg, DB: conn})

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
