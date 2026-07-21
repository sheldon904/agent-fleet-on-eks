// Command notify-bridge is a small HTTP service that verifies signed requests and fans a
// notification out to ntfy and/or Telegram concurrently. It is a Go port of a Python service
// in the agent fleet; see NOTES.md for the operational diff observed after porting.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	cfg, err := LoadConfig()
	if err != nil {
		log.Error("configuration error", "err", err.Error())
		os.Exit(1)
	}

	notifier := NewNotifier(cfg)
	log.Info("starting notify-bridge", "port", cfg.Port, "targets", notifier.TargetNames())
	if !cfg.AnyTargetEnabled() {
		log.Warn("no notification targets configured; /readyz will report not ready")
	}

	verifier := NewHMACVerifier(cfg.HMACSecret)
	srv := NewServer(notifier, verifier, cfg.AnyTargetEnabled, log)

	httpServer := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           srv.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Cancel ctx on SIGINT/SIGTERM so Kubernetes pod termination drains cleanly.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("server failed", "err", err.Error())
			stop()
		}
	}()

	<-ctx.Done()
	log.Info("shutdown signal received; draining in-flight requests")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		log.Error("graceful shutdown failed", "err", err.Error())
		os.Exit(1)
	}
	log.Info("stopped cleanly")
}
