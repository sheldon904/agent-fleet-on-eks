package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

// fakeTarget is a controllable Target for tests.
type fakeTarget struct {
	name  string
	ok    bool
	delay time.Duration
	calls int32
}

func (f *fakeTarget) Name() string { return f.name }

func (f *fakeTarget) Send(ctx context.Context, _ *http.Client, _ Message) Result {
	atomic.AddInt32(&f.calls, 1)
	select {
	case <-time.After(f.delay):
		return Result{OK: f.ok, Status: 200}
	case <-ctx.Done():
		return Result{OK: false, Error: ctx.Err().Error()}
	}
}

func newTestNotifier(timeout time.Duration, targets ...Target) *Notifier {
	return &Notifier{targets: targets, client: http.DefaultClient, timeout: timeout}
}

func TestNotifyFanOut(t *testing.T) {
	a := &fakeTarget{name: "a", ok: true}
	b := &fakeTarget{name: "b", ok: false}
	n := newTestNotifier(time.Second, a, b)

	results := n.Notify(context.Background(), Message{Message: "hello"})
	if len(results) != 2 {
		t.Fatalf("want 2 results, got %d", len(results))
	}
	got := map[string]bool{}
	for _, r := range results {
		got[r.Target] = r.OK
	}
	if !got["a"] || got["b"] {
		t.Fatalf("unexpected results: %+v", got)
	}
	if atomic.LoadInt32(&a.calls) != 1 || atomic.LoadInt32(&b.calls) != 1 {
		t.Fatalf("each target should be called once: a=%d b=%d", a.calls, b.calls)
	}
}

func TestNotifyRespectsTimeout(t *testing.T) {
	slow := &fakeTarget{name: "slow", ok: true, delay: time.Second}
	n := newTestNotifier(20*time.Millisecond, slow)

	start := time.Now()
	results := n.Notify(context.Background(), Message{Message: "hi"})
	elapsed := time.Since(start)

	if elapsed > 500*time.Millisecond {
		t.Fatalf("Notify did not honor timeout; took %s", elapsed)
	}
	if results[0].OK {
		t.Fatalf("slow target should have failed on context deadline")
	}
}

func TestNtfyTargetSend(t *testing.T) {
	var gotTitle string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotTitle = r.Header.Get("Title")
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	tgt := &ntfyTarget{NtfyConfig{BaseURL: srv.URL, Topic: "alerts"}}
	res := tgt.Send(context.Background(), http.DefaultClient, Message{Title: "T", Message: "m"})
	if !res.OK || res.Status != 200 {
		t.Fatalf("want ok 200, got %+v", res)
	}
	if gotTitle != "T" {
		t.Fatalf("want Title header 'T', got %q", gotTitle)
	}
}

func TestNtfyTargetNon2xx(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	tgt := &ntfyTarget{NtfyConfig{BaseURL: srv.URL, Topic: "alerts"}}
	res := tgt.Send(context.Background(), http.DefaultClient, Message{Message: "m"})
	if res.OK {
		t.Fatalf("want failure on 500, got %+v", res)
	}
}
