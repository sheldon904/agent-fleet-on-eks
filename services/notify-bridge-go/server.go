package main

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"time"
)

// maxBodyBytes caps the inbound request body to keep signature verification bounded.
const maxBodyBytes = 1 << 20 // 1 MiB

// Server wires the HTTP handlers to the notifier and signature verifier.
type Server struct {
	notifier *Notifier
	verifier *HMACVerifier
	ready    func() bool
	log      *slog.Logger
}

// NewServer constructs a Server.
func NewServer(n *Notifier, v *HMACVerifier, ready func() bool, log *slog.Logger) *Server {
	return &Server{notifier: n, verifier: v, ready: ready, log: log}
}

// Routes returns the HTTP handler with logging middleware applied.
func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("GET /readyz", s.handleReadyz)
	mux.HandleFunc("POST /notify", s.handleNotify)
	return s.logRequests(mux)
}

// handleHealthz is the liveness probe: always OK once the process is serving.
func (s *Server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// handleReadyz is the readiness probe: OK only when a target is configured.
func (s *Server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	if s.ready == nil || s.ready() {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ready", "targets": s.notifier.TargetNames()})
		return
	}
	writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "not ready"})
}

// handleNotify verifies the request signature, then fans the message out to every target.
func (s *Server) handleNotify(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "cannot read body"})
		return
	}

	if err := s.verifier.Verify(r.Header.Get(signatureHeader), body); err != nil {
		s.log.Warn("rejected notify: bad signature", "err", err.Error())
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid signature"})
		return
	}

	var msg Message
	if err := json.Unmarshal(body, &msg); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}
	if msg.Message == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "message is required"})
		return
	}

	results := s.notifier.Notify(r.Context(), msg)

	okCount := 0
	for _, res := range results {
		if res.OK {
			okCount++
		}
	}

	// Map delivery outcome onto a status code the caller can act on.
	status := http.StatusOK
	switch {
	case len(results) == 0:
		status = http.StatusServiceUnavailable // no targets configured
	case okCount == 0:
		status = http.StatusBadGateway // every target failed
	case okCount < len(results):
		status = http.StatusMultiStatus // partial delivery
	}

	writeJSON(w, status, map[string]any{
		"delivered": okCount,
		"targets":   len(results),
		"results":   results,
	})
}

// writeJSON writes v as a JSON response with the given status code.
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// statusRecorder captures the response status for request logging.
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

// logRequests emits one structured log line per request.
func (s *Server) logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		s.log.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", rec.status,
			"dur", time.Since(start).Round(time.Millisecond).String(),
		)
	})
}
