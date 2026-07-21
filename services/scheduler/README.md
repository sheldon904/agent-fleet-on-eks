# scheduler

Pulls pending tickets and drives each one through the trust ladder: request a one-shot
`open_pr` token from governance-mcp, then dispatch the ticket + token to the runner. Reference
stand-in, stdlib only.

## Endpoints

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET | `/healthz` `/readyz` | — | probes |
| GET | `/status` | — | pending count + recent processed results |
| POST | `/enqueue` | `{id, title, body, repo}` | add a ticket to the queue |

A background worker drains the queue every `POLL_INTERVAL` seconds.

## Config

| Var | Default | Notes |
|-----|---------|-------|
| `GOVERNANCE_URL` | `http://governance-mcp:8080` | |
| `RUNNER_URL` | `http://ticket-to-pr-runner:8080` | |
| `POLL_INTERVAL` | `5` | seconds between drains |
| `PORT` | `8080` | |

## Test

```bash
python -m unittest -v
```
