# governance-mcp

The trust core of the fleet (reference stand-in, stdlib only). Three controls:

- **Default-deny trust ladder** — a caller may only request actions explicitly granted to it.
- **One-shot action tokens** — HMAC-signed, single-use, time-bounded capabilities.
- **Append-only, hash-chained audit stream** — tamper-evident, mirrored to stdout.

## Endpoints

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET | `/healthz` `/readyz` | — | probes |
| POST | `/token` | `{caller, action, subject}` | issue a one-shot token (403 if not on the ladder) |
| POST | `/verify` | `{token}` | verify + consume a token (401 on invalid/expired/replayed) |
| POST | `/audit` | `{event, details}` | append an audit record |
| GET | `/audit` | — | recent events + `chain_valid` |

## Config

| Var | Default | Notes |
|-----|---------|-------|
| `GOV_HMAC_SECRET` / `_FILE` | insecure dev default (warns) | token signing key |
| `TRUST_LADDER` | `{"scheduler":["open_pr"]}` | JSON: caller → allowed actions |
| `AUDIT_LOG_PATH` | `audit.log` | append-only log path (mount a volume) |
| `PORT` | `8080` | |

## Test

```bash
python -m unittest -v          # from this directory
```
