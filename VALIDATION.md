# Validation — what's proven, and what needs a live account

Honest accounting of how far this repo is verified, so a reviewer knows exactly what's been run.

## Verified locally (no AWS)

| Check | How | Result |
|-------|-----|--------|
| governance-mcp unit tests | `python -m unittest` (trust ladder, one-shot tokens, expiry, tamper, audit hash chain) | pass |
| scheduler unit tests | fake-poster tests: token-then-dispatch, deny-blocks-dispatch, drain | pass |
| ticket-to-pr-runner unit tests | fake-http tests: dry-run PR, token verify gate, subject/action mismatch, exact-body HMAC signing | pass |
| **End-to-end pipeline** | `python scripts/e2e_local.py` — governance + runner as real HTTP servers + mock notify target, one ticket driven by the scheduler | **pass**: `token.issued → token.consumed`, PR produced, notify HMAC-verified, audit `chain_valid=True` |

The e2e is the important one: it proves the whole trust flow (scheduler → governance token →
runner → PR → signed notification, all on the audit stream) with real sockets and real HMAC
verification.

## Validated by CI (see `.github/workflows/ci.yml`)

Runs on every PR — catches what can't be validated in the authoring environment (which has no
Go, Terraform, or Helm):

- **Go bridge**: `go vet`, `go test -race`, `go build` (table-driven tests incl. context-timeout and HMAC tampering).
- **Terraform**: `terraform fmt -check` + `terraform init && validate` on `envs/dev` (resolves the real VPC/EKS module APIs).
- **Helm**: `helm lint` + `helm template` + `kubeconform` on the rendered manifests.
- **Python + e2e**: the same tests as above, on Linux.

## Requires a live AWS account (the "clean-room" run)

These can only be proven against real infrastructure and are the operator's step (the runbook
walks through each):

- `terraform apply` → a reachable EKS cluster, then `terraform destroy` clean.
- Secrets Store CSI actually mounting Secrets Manager values into pods.
- A **real ticket end-to-end on the cluster** opening a genuine GitHub PR (`DRY_RUN=false`).
- The timed **fresh-account → running fleet in < 1 hour** walkthrough.
- The CD approval gate pausing a real rollout until a reviewer approves.

## DONE-WHEN checklist

| Criterion | Status |
|-----------|--------|
| Fresh AWS account → running fleet in < 1 hr via the runbook | runbook written + timed steps; **needs the live clean-room run to certify the time** |
| Ticket-to-PR pipeline completes one ticket end-to-end | **pipeline logic proven locally**; real GitHub PR on-cluster needs the live account |
| Repo public + linked in application | operator action (outward-facing) |

## Reproduce the local checks

```bash
# unit tests
for d in governance-mcp scheduler ticket-to-pr-runner; do ( cd services/$d && python -m unittest ); done
# end-to-end
python scripts/e2e_local.py        # exits 0 on success
```
