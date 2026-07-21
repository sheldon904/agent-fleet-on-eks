# services/ — application code

The agent fleet's services. See [`../PLAN.md`](../PLAN.md) Phases 2 & 3.

## Planned layout

```
services/
├── governance-mcp/        # governance MCP server (audit stream, action tokens, trust ladder)
├── scheduler/             # job scheduler
├── ticket-to-pr-runner/   # ticket → PR pipeline
├── notify-bridge-go/      # NEW: ntfy/Telegram bridge, rewritten in Go (Gap 5)
└── docker-compose.yml     # direct-backend variant (Docker), mirrors the K8s stack
```

## Existing services — import vs. scaffold (Phase 0 decision)

This repo starts empty. Default plan is **(B) scaffold faithful reference stand-ins** for the
three existing services so the whole system runs and the runbook is real; swap in production
code later if available. See [`../PLAN.md`](../PLAN.md#assumption-to-confirm-phase-0-decision).

## notify-bridge-go — the Go port (Gap 5)

Fresh Go implementation regardless of the decision above:

- HTTP server: `/healthz`, `/readyz`, `/notify`.
- **Goroutine fan-out** to ntfy + Telegram concurrently.
- **`context` cancellation** + per-request timeouts on outbound calls.
- A single **reused `http.Client`** with real timeouts (not `http.DefaultClient`).
- HMAC verification of inbound requests using the Secrets Manager key.
- Table-driven tests; distroless/static, non-root `Dockerfile`.
- `NOTES.md`: the concrete before/after operational diff (startup, memory, image size,
  concurrency).
