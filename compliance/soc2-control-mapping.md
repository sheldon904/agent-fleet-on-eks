# SOC 2 control mapping — agent-fleet-on-eks

How the fleet's controls map to the **SOC 2 Trust Services Criteria (TSC 2017, rev. 2022)**.

> **Scope note.** This is a *control-to-criteria mapping* to demonstrate that the reference
> deployment is built with SOC 2 in mind. It is **not** a claim of certification. In a real
> Type II engagement an auditor tests whether each control was *suitably designed* and
> *operated effectively over a period* (typically 3–12 months) by sampling the evidence in the
> last column. Where a customer runs this fleet themselves, several items become
> **Complementary User-Entity Controls (CUECs)** — noted inline.

## Primer terms used here

- **Criterion vs. control.** The TSC define *criteria* (what must be true); the entity designs
  *controls* to meet them. One control can support several criteria and vice-versa.
- **Common Criteria (CC1–CC9)** cover the Security category and always apply. **Availability
  (A)**, **Confidentiality (C)**, and **Processing Integrity (PI)** apply if in scope.
- **Type II** = design *and* operating effectiveness over time (vs. Type I = design at a point
  in time).

## Mapping

| # | Control (as built here) | Where in the repo | TSC criteria supported | Evidence an auditor would sample |
|---|---|---|---|---|
| 1 | **Append-only, hash-chained audit stream** — every governance decision recorded; each record commits to the previous record's hash; mirrored to stdout (→ cluster log pipeline) | `services/governance-mcp/app.py` (`audit`, `verify_chain`) | CC7.2, CC7.3, PI1.4 | Sample audit records; re-run `verify_chain`; confirm log shipping retains them |
| 2 | **One-shot action tokens** — HMAC-signed, single-use, time-bounded capabilities; replay is rejected and logged | `services/governance-mcp/app.py` (`issue_token`, `verify_and_consume`) | CC6.1, PI1.2, PI1.5 | Attempt a token replay in a test account; confirm `token.replay` audit event and 401 |
| 3 | **Default-deny trust ladder** — a caller may request only the actions explicitly granted to it; all else denied and audited | `services/governance-mcp/app.py` (`allowed`), `TRUST_LADDER` value | CC6.1, CC6.2, CC6.3 | Review the trust-ladder config; test a denied caller → `token.denied` |
| 4 | **Default-deny network isolation** — namespace-wide deny (ingress+egress), explicit per-service allow rules only | `charts/agent-fleet/templates/networkpolicy.yaml` | CC6.6, CC6.7 | `kubectl get networkpolicy`; test a disallowed pod-to-pod connection is refused |
| 5 | **Secret management + rotation** — HMAC keys/API tokens in AWS Secrets Manager, mounted via CSI (kept out of etcd), never in Git or env vars | `terraform/modules/secrets`, `charts/agent-fleet/templates/secretproviderclass.yaml` | CC6.1, CC6.7, C1.1 | Confirm no secrets in Git/etcd; review rotation cadence (CUEC: customer sets rotation) |
| 6 | **Least-privilege workload identity (IRSA)** — each ServiceAccount assumes an IAM role scoped to just its own secret; no node-wide creds | `terraform/modules/irsa`, `envs/dev/main.tf` (`module.irsa`) | CC6.1, CC6.3 | Review each role's policy; confirm a workload cannot read another's secret |
| 7 | **Immutable, scanned images** — immutable ECR tags (SHA-pinned), scan-on-push, distroless/non-root runtime | `terraform/modules/ecr`, service `Dockerfile`s | CC6.8, CC7.1 | Review scan findings; confirm tags are immutable and images run as non-root |
| 8 | **Change management with human approval** — IaC for all infra; CI tests + build; deploy gated on a required reviewer | `.github/workflows/*.yml`, `terraform/` | CC8.1 | Sample a deploy run showing the approval step; confirm reviewers configured |
| 9 | **Keyless CI identity** — GitHub Actions assumes a scoped AWS role via OIDC; no static keys stored | `terraform/modules/github-oidc`, `.github/workflows/cd.yml` | CC6.1, CC6.6 | Confirm no AWS keys in GitHub secrets; review the role's trust + permissions |
| 10 | **Hardened, healthy workloads** — liveness/readiness probes, resource limits, non-root, read-only rootfs, dropped caps, node autoscaling | `charts/agent-fleet/templates/deployment.yaml`, `terraform/modules/eks` | A1.1, A1.2, CC6.8 | Review pod securityContext + limits; confirm probes and autoscaling config |
| 11 | **Private network topology** — nodes in private subnets, egress via NAT, API endpoint restrictable to known CIDRs | `terraform/modules/vpc`, `terraform/modules/eks` | CC6.6, CC6.7 | Review subnet routing; confirm nodes have no public IPs |

## Criteria coverage summary

| Category | Criteria touched |
|---|---|
| Security (Common Criteria) | CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC6.8, CC7.1, CC7.2, CC7.3, CC8.1 |
| Availability | A1.1, A1.2 |
| Confidentiality | C1.1 |
| Processing Integrity | PI1.2, PI1.4, PI1.5 |

## Complementary User-Entity Controls (what the customer must own)

- Set and enforce a **secret rotation** cadence in Secrets Manager (control #5).
- Configure **required reviewers** on the `production` environment (control #8).
- Restrict the **API endpoint CIDRs** and review the trust ladder for their org (controls #3, #11).
- Ship the **audit stream** to durable, access-controlled storage with a defined retention
  period, and monitor/alert on `token.denied` / `token.replay` (controls #1, #2).
