# notify-bridge (Go)

The ntfy/Telegram notification bridge for the agent fleet, ported to Go (Gap 5). Verifies an
HMAC signature on inbound requests, then fans the message out to every configured target
concurrently. Standard library only — no third-party dependencies.

See [`NOTES.md`](./NOTES.md) for the operational diff observed after porting from Python.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Liveness — always 200 while serving |
| GET | `/readyz` | Readiness — 200 only when ≥1 target is configured |
| POST | `/notify` | HMAC-verified; fans out to targets |

`POST /notify` body:

```json
{ "title": "Deploy", "message": "ticket #42 shipped", "priority": "high", "tags": ["rocket"] }
```

Response maps delivery to a status code: `200` all delivered, `207` partial, `502` all failed,
`503` no targets configured. Body includes per-target results.

## Configuration (environment)

| Var | Required | Notes |
|-----|----------|-------|
| `HMAC_SECRET` / `HMAC_SECRET_FILE` | yes | Shared secret for request signatures. `_FILE` reads a CSI-mounted secret. |
| `PORT` | no | Default `8080`. |
| `REQUEST_TIMEOUT` | no | Per-fan-out deadline, e.g. `5s`. Default `5s`. |
| `NTFY_URL`, `NTFY_TOPIC` | for ntfy | Both required to enable the ntfy target. |
| `NTFY_TOKEN` / `NTFY_TOKEN_FILE` | no | Bearer token for a protected ntfy server. |
| `TELEGRAM_BOT_TOKEN` / `..._FILE`, `TELEGRAM_CHAT_ID` | for Telegram | Both required to enable Telegram. |

Every `*_FILE` variant lets Kubernetes mount the value as a file via the AWS Secrets Store CSI
driver instead of exposing it as an environment variable.

## Develop

```bash
go test ./...              # unit tests (table-driven; httptest; context-timeout coverage)
go vet ./...
go build -o notify-bridge .

# Run locally against a local ntfy
HMAC_SECRET=dev NTFY_URL=https://ntfy.sh NTFY_TOPIC=agent-fleet-demo ./notify-bridge
```

Send a signed request:

```bash
BODY='{"message":"hello from the fleet"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "dev" -hex | awk '{print $2}')
curl -sS -X POST localhost:8080/notify \
  -H "X-Signature-256: sha256=$SIG" \
  -d "$BODY"
```

## Build the image

```bash
docker build -t notify-bridge:dev .
```

Multi-stage → `gcr.io/distroless/static:nonroot`. Runs as non-root, no shell, no libc.
