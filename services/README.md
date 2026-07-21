# services/ — application code

The agent fleet's services. See [`../PLAN.md`](../PLAN.md) Phases 2 & 3.

## Layout

```
services/
├── governance-mcp/        # governance MCP server (audit stream, action tokens, trust ladder)
├── scheduler/             # job scheduler
├── ticket-to-pr-runner/   # ticket → PR pipeline
├── notify-bridge-go/      # ntfy/Telegram bridge, rewritten in Go (Gap 5)
└── docker-compose.yml     # direct-backend variant (Docker), mirrors the K8s stack
```

## Reference stand-ins vs. the Go port

The three Python services (`governance-mcp`, `scheduler`, `ticket-to-pr-runner`) are faithful
reference stand-ins — stdlib-only implementations that exhibit the real behaviors (append-only
audit stream, one-shot action tokens, default-deny trust ladder, ticket→PR flow) so the whole
system runs and the runbook is real. Production code can be swapped in later without changing
the charts, IRSA wiring, or NetworkPolicies. See
[`../PLAN.md`](../PLAN.md#assumption-to-confirm-phase-0-decision).

Each service ships unit tests (`python -m unittest` from its directory), and
[`../scripts/e2e_local.py`](../scripts/e2e_local.py) drives one ticket through all of them end
to end. `docker-compose.yml` runs the same stack locally.

## notify-bridge-go — the Go port (Gap 5)

A fresh Go implementation (the only service written from scratch rather than stood in):

- HTTP server: `/healthz`, `/readyz`, `/notify`.
- **Goroutine fan-out** to ntfy + Telegram concurrently.
- **`context` cancellation** + per-request timeouts on outbound calls.
- A single **reused `http.Client`** with real timeouts (not `http.DefaultClient`).
- HMAC verification of inbound requests using the Secrets Manager key.
- Table-driven tests; distroless/static, non-root `Dockerfile`.
- `NOTES.md`: the concrete before/after operational diff (startup, memory, image size,
  concurrency).
