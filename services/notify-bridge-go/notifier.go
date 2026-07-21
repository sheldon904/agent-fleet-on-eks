package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

// Message is the inbound notification payload.
type Message struct {
	Title    string   `json:"title"`
	Message  string   `json:"message"`
	Priority string   `json:"priority,omitempty"`
	Tags     []string `json:"tags,omitempty"`
}

// Result is the per-target outcome of a fan-out.
type Result struct {
	Target  string `json:"target"`
	OK      bool   `json:"ok"`
	Status  int    `json:"status,omitempty"`
	Error   string `json:"error,omitempty"`
	Latency string `json:"latency"`
}

// Target is one notification backend (ntfy, Telegram, ...).
type Target interface {
	Name() string
	Send(ctx context.Context, client *http.Client, msg Message) Result
}

// Notifier fans a Message out to every configured Target concurrently over one shared client.
type Notifier struct {
	targets []Target
	client  *http.Client
	timeout time.Duration
}

// NewNotifier wires up the enabled targets and a single reused HTTP client.
func NewNotifier(cfg Config) *Notifier {
	// One shared, reused client with bounded connection pooling. We deliberately do NOT set
	// client.Timeout; per-request deadlines come from context (see Notify) so a slow target
	// cancels cleanly without tearing down the shared transport for the others.
	client := &http.Client{
		Transport: &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     90 * time.Second,
		},
	}

	var targets []Target
	if cfg.Ntfy.Enabled() {
		targets = append(targets, &ntfyTarget{cfg.Ntfy})
	}
	if cfg.Telegram.Enabled() {
		targets = append(targets, &telegramTarget{cfg.Telegram})
	}

	return &Notifier{targets: targets, client: client, timeout: cfg.RequestTimeout}
}

// TargetNames returns the names of the configured targets.
func (n *Notifier) TargetNames() []string {
	names := make([]string, len(n.targets))
	for i, t := range n.targets {
		names[i] = t.Name()
	}
	return names
}

// Notify sends msg to all targets in parallel and returns one Result per target. The parent
// context is honored (an inbound client disconnect cancels every in-flight send), and each
// fan-out additionally gets n.timeout as a deadline.
func (n *Notifier) Notify(ctx context.Context, msg Message) []Result {
	ctx, cancel := context.WithTimeout(ctx, n.timeout)
	defer cancel()

	results := make([]Result, len(n.targets))
	var wg sync.WaitGroup
	for i, t := range n.targets {
		wg.Add(1)
		go func(i int, t Target) {
			defer wg.Done()
			start := time.Now()
			r := t.Send(ctx, n.client, msg)
			r.Target = t.Name()
			r.Latency = time.Since(start).Round(time.Millisecond).String()
			results[i] = r
		}(i, t)
	}
	wg.Wait()
	return results
}

// ---- ntfy target ----

type ntfyTarget struct{ cfg NtfyConfig }

func (t *ntfyTarget) Name() string { return "ntfy" }

func (t *ntfyTarget) Send(ctx context.Context, client *http.Client, msg Message) Result {
	endpoint := t.cfg.BaseURL + "/" + t.cfg.Topic
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader([]byte(msg.Message)))
	if err != nil {
		return Result{OK: false, Error: err.Error()}
	}
	if msg.Title != "" {
		req.Header.Set("Title", msg.Title)
	}
	if msg.Priority != "" {
		req.Header.Set("Priority", msg.Priority)
	}
	if len(msg.Tags) > 0 {
		req.Header.Set("Tags", strings.Join(msg.Tags, ","))
	}
	if t.cfg.Token != "" {
		req.Header.Set("Authorization", "Bearer "+t.cfg.Token)
	}
	return do(client, req)
}

// ---- Telegram target ----

type telegramTarget struct{ cfg TelegramConfig }

func (t *telegramTarget) Name() string { return "telegram" }

func (t *telegramTarget) Send(ctx context.Context, client *http.Client, msg Message) Result {
	endpoint := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", t.cfg.BotToken)
	text := msg.Message
	if msg.Title != "" {
		text = "*" + msg.Title + "*\n" + msg.Message
	}
	body, _ := json.Marshal(map[string]string{
		"chat_id":    t.cfg.ChatID,
		"text":       text,
		"parse_mode": "Markdown",
	})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return Result{OK: false, Error: err.Error()}
	}
	req.Header.Set("Content-Type", "application/json")
	return do(client, req)
}

// do executes req and maps the response into a Result, draining the body so the underlying
// connection can be reused by the shared client.
func do(client *http.Client, req *http.Request) Result {
	resp, err := client.Do(req)
	if err != nil {
		return Result{OK: false, Error: err.Error()}
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)

	ok := resp.StatusCode >= 200 && resp.StatusCode < 300
	r := Result{OK: ok, Status: resp.StatusCode}
	if !ok {
		r.Error = fmt.Sprintf("non-2xx response: %d", resp.StatusCode)
	}
	return r
}
