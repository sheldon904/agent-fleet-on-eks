package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func testServer(targets ...Target) *Server {
	n := &Notifier{targets: targets, client: http.DefaultClient, timeout: time.Second}
	v := NewHMACVerifier([]byte("test-secret"))
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	return NewServer(n, v, func() bool { return len(targets) > 0 }, log)
}

func TestHandleHealthz(t *testing.T) {
	s := testServer(&fakeTarget{name: "a", ok: true})
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("want 200, got %d", rec.Code)
	}
}

func TestHandleReadyzNoTargets(t *testing.T) {
	s := testServer() // no targets configured
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("want 503, got %d", rec.Code)
	}
}

func TestHandleNotifyValidSignature(t *testing.T) {
	tgt := &fakeTarget{name: "a", ok: true}
	s := testServer(tgt)

	body := []byte(`{"message":"deployed"}`)
	sig := s.verifier.Compute(body)

	req := httptest.NewRequest(http.MethodPost, "/notify", bytes.NewReader(body))
	req.Header.Set(signatureHeader, sig)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("want 200, got %d (%s)", rec.Code, rec.Body.String())
	}
	var resp struct {
		Delivered int `json:"delivered"`
		Targets   int `json:"targets"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &resp)
	if resp.Delivered != 1 || resp.Targets != 1 {
		t.Fatalf("want delivered=1 targets=1, got %+v", resp)
	}
}

func TestHandleNotifyBadSignature(t *testing.T) {
	s := testServer(&fakeTarget{name: "a", ok: true})
	req := httptest.NewRequest(http.MethodPost, "/notify", bytes.NewReader([]byte(`{"message":"x"}`)))
	req.Header.Set(signatureHeader, "sha256=deadbeef")
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", rec.Code)
	}
}

func TestHandleNotifyMissingMessage(t *testing.T) {
	s := testServer(&fakeTarget{name: "a", ok: true})
	body := []byte(`{"title":"only title"}`)
	sig := s.verifier.Compute(body)
	req := httptest.NewRequest(http.MethodPost, "/notify", bytes.NewReader(body))
	req.Header.Set(signatureHeader, sig)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("want 400, got %d", rec.Code)
	}
}

func TestHandleNotifyPartialDelivery(t *testing.T) {
	s := testServer(&fakeTarget{name: "a", ok: true}, &fakeTarget{name: "b", ok: false})
	body := []byte(`{"message":"x"}`)
	sig := s.verifier.Compute(body)
	req := httptest.NewRequest(http.MethodPost, "/notify", bytes.NewReader(body))
	req.Header.Set(signatureHeader, sig)
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	if rec.Code != http.StatusMultiStatus {
		t.Fatalf("want 207, got %d", rec.Code)
	}
}
