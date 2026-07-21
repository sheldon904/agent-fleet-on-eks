# ticket-to-pr-runner

Turns a ticket into a pull request, under governance. Reference stand-in, stdlib only.

`POST /run {ticket, token}`:
1. Re-verify + consume the one-shot token with governance-mcp (action must be `open_pr`,
   subject must equal the ticket id).
2. Open a PR — dry-run by default; real GitHub API when `DRY_RUN=false` with a token + repo.
3. Announce via the notify-bridge with an HMAC-signed request.

## Endpoints

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET | `/healthz` `/readyz` | — | probes |
| POST | `/run` | `{ticket, token}` | verify token → open PR → notify |

## Config

| Var | Default | Notes |
|-----|---------|-------|
| `GOVERNANCE_URL` | `http://governance-mcp:8080` | |
| `NOTIFY_URL` | `http://notify-bridge:8080` | |
| `NOTIFY_HMAC_SECRET` / `_FILE` | insecure dev default | **must match** the notify-bridge `HMAC_SECRET` |
| `GITHUB_TOKEN` | — | required for a real PR |
| `GITHUB_REPO` | — | `owner/name`, required for a real PR |
| `BASE_BRANCH` | `main` | |
| `DRY_RUN` | `true` | set `false` for a real GitHub PR |
| `PORT` | `8080` | |

## Test

```bash
python -m unittest -v
```
