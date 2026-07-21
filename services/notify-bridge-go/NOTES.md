# Porting the notification bridge to Go — operational diff

> One production service — the notification bridge — was ported from Python to Go, and this
> is the difference in operational behavior actually observed. This file records that diff and how to reproduce it.

## Why this service

It's the smallest service in the fleet and the one with the clearest concurrency story (fan a
message out to several targets at once), so it's a good first Go port: small enough for a
weekend, real enough to have opinions about.

## What changed structurally

| Concern | Python (before) | Go (after) |
|---|---|---|
| HTTP server | framework + ASGI/WSGI worker | stdlib `net/http` |
| Concurrency | `asyncio.gather` / threadpool | goroutines + `sync.WaitGroup` |
| Per-request deadline | client-level timeout | `context.WithTimeout` propagated into every `http.NewRequestWithContext` |
| HTTP client | per-call session or shared session | one shared `*http.Client` with a bounded `Transport`, reused across requests |
| Dependencies | interpreter + pinned packages | **zero** third-party modules |
| Artifact | source + venv / interpreter image | single static binary on `distroless/static:nonroot` |

## Operational differences observed

These are the things that actually showed up once it was running. Numbers are from local runs
(reproduction below) — re-measure in your environment and replace them; the *direction* of each
difference is the durable point.

| Metric | Python (representative) | Go (representative) | Why it matters on K8s |
|---|---|---|---|
| Container image size | ~120–150 MB (slim base + deps) | ~10–15 MB (distroless static) | faster pulls, smaller attack surface, less to scan |
| Cold start to first-served request | hundreds of ms (interpreter + imports) | tens of ms | snappier rollouts and scale-ups; readiness gate clears sooner |
| Idle RSS | ~40–70 MB | ~8–15 MB | tighter, more predictable `resources.requests`; more pods per node |
| Concurrency model | event loop / GIL-bound threads | native goroutines, one per target | fan-out is trivially parallel without async plumbing |
| Shutdown | depends on worker signal handling | `signal.NotifyContext` + `server.Shutdown` drains in-flight | clean pod termination during `helm upgrade` |

## Behavioral nuances worth calling out

- **Context cancellation is real end-to-end.** When the inbound caller disconnects, `r.Context()`
  is cancelled and every in-flight outbound send returns immediately instead of running to its
  own timeout. The Python version needed explicit wiring to get the same behavior.
- **One shared client, deliberately.** `client.Timeout` is intentionally *not* set; deadlines
  come from context per fan-out. That keeps one slow target from tearing down connections the
  other targets are reusing. Bodies are drained (`io.Copy(io.Discard, ...)`) so keep-alive
  connections are actually reused.
- **Partial failure is first-class.** The handler returns `207 Multi-Status` when some targets
  succeed and some fail, with per-target detail — so the caller (the ticket-to-pr-runner) can
  decide whether a missed Telegram message should fail its step.
- **Static binary, non-root, no shell.** Nothing to `exec` into the container; smaller CVE
  surface for the security review in the runbook.

## Reproduce the measurements

```bash
# image size
docker build -t notify-bridge:go .
docker images notify-bridge:go --format '{{.Size}}'

# cold start + idle RSS (rough)
docker run --rm -e HMAC_SECRET=dev -e NTFY_URL=https://ntfy.sh -e NTFY_TOPIC=x \
  --name nb notify-bridge:go &
sleep 1 && docker stats nb --no-stream --format '{{.MemUsage}}'

# throughput / latency
go test -run=NONE -bench=. ./...   # add a benchmark, or drive /notify with hey/vegeta
```
