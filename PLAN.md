# Build Plan — agent-fleet-on-eks

**Goal:** One reference deployment that closes gaps 1–5 and produces the artifact a
forward-deployed engineer actually hands over — reusable implementation patterns and
documentation.

**Effort:** ~2–3 weekends. Terraform/EKS is the bulk.

**Done when:**
1. A fresh AWS account can go from empty to a running fleet **in under an hour** by following
   the runbook, and
2. The ticket-to-PR pipeline completes **one real ticket end-to-end** on the cluster.

---

## Guiding constraints

- **Minimal but real.** Every component must actually run and be destroyable/recreatable
  cleanly. No mock infra.
- **Cheap.** Default to the smallest thing that demonstrates the pattern. Tear down between
  sessions; document the cost.
- **Customer-facing voice.** Docs are written for a customer's platform engineer, not for us.
- **The air-gap instinct, in K8s vocabulary.** Default-deny NetworkPolicy with explicit allow
  rules; secrets out of env vars and into Secrets Manager; least-privilege IRSA.

## Assumption to confirm (Phase 0 decision)

This repo starts empty, so the "existing services" (governance MCP server, scheduler,
ticket-to-PR runner, notification bridge) are **not present here**. Two options:

- **(A) Import real code** — drop the existing services into `services/` and containerize them.
- **(B) Scaffold reference stand-ins** *(default)* — build minimal but faithful reference
  implementations that exhibit the described behaviors (append-only audit stream, one-shot
  action tokens, default-deny trust ladder, ticket→PR flow) so the whole system runs and the
  runbook is real, then swap in the production code later.

**Default chosen: (B) scaffold reference stand-ins**, because the deliverable is the *pattern
and the runbook*, and a runnable system is worth more than a stub. The Go notification bridge
(gap 5) is written fresh regardless. If the real services are available, we switch to (A) for
those and keep everything else identical.

---

## Phase 0 — Scaffold & decisions  *(this session, ~1 hr)*

**Deliverables**
- [x] Repo layout: `terraform/ charts/ services/ .github/ runbook/ compliance/`
- [x] Top-level `README.md` with architecture diagram, repo map, cost table, teardown note
- [x] This `PLAN.md`
- [x] `.gitignore` (Terraform state, Go/Node build output, secrets, `.env`)
- [x] Per-directory briefs that carry the plan for each section
- [ ] Confirm A vs. B for existing services (defaulting to B)

**Acceptance:** `git` tree matches the spec layout; a reader understands the whole project
from `README.md` + `PLAN.md`.

---

## Phase 1 — Terraform foundation  *(Weekend 1, the bulk)*  → closes Gap 2

Minimal-but-real cloud footprint, destroy/recreate clean.

**Modules / resources**
- `terraform/modules/vpc/` — VPC, 2 AZs, public + **private** subnets, 1 NAT Gateway,
  route tables. (1 NAT, not 3, to keep cost down — noted as a documented trade-off.)
- `terraform/modules/eks/` — EKS cluster + **one managed node group** (2× `t3.medium`,
  autoscale 1–3), OIDC provider for IRSA, cluster security groups.
- `terraform/modules/irsa/` — IAM roles for service accounts: one role per workload that
  needs AWS access (e.g. `notify-bridge` → read its Secrets Manager secret only;
  `ticket-to-pr` → read its token). Least privilege.
- `terraform/modules/ecr/` — one ECR repo per service, lifecycle policy to expire untagged.
- `terraform/modules/secrets/` — Secrets Manager entries for the HMAC keys and API tokens
  currently in env vars (values injected out-of-band, never committed).
- `terraform/envs/dev/` — root module wiring the above; `terraform.tfvars.example`.
- Remote state: S3 + DynamoDB lock (bootstrapped by a small `terraform/bootstrap/` or
  documented as a one-time manual step).

**Talking points to capture in the runbook**
- Why private subnets + IRSA instead of node instance-profile creds.
- The 1-NAT cost trade-off and how to make it HA in production.

**Acceptance**
- `terraform apply` from zero produces a reachable cluster (`kubectl get nodes` = Ready).
- `terraform destroy` leaves nothing billable behind (verify in Cost Explorer / no orphaned
  ENIs, EIPs, LBs).
- Time-to-cluster recorded (feeds the "under an hour" claim).

---

## Phase 2 — Workloads: Helm + K8s hardening  *(Weekend 2)*  → closes Gap 1

Each service as a Deployment with the production hygiene a platform team expects.

**Per service (`governance-mcp`, `scheduler`, `ticket-to-pr-runner`, `notify-bridge`)**
- Helm chart in `charts/<service>/` (umbrella `charts/agent-fleet/` optional) with:
  - Deployment: liveness + readiness probes, `resources.requests/limits`, non-root
    `securityContext`, read-only root FS where possible.
  - ServiceAccount annotated for **IRSA**.
  - Secrets via **AWS Secrets Store CSI driver** (mounted as files, kept out of etcd) — with
    a documented fallback to External Secrets Operator.
- **Default-deny NetworkPolicy** for the namespace, plus explicit allow rules:
  - DNS egress, governance-mcp ↔ its clients, runner → GitHub (egress), notify-bridge →
    ntfy/Telegram (egress). Everything else denied. This is the air-gap instinct in K8s.

**Direct-backend variant (docs)**
- `runbook/direct-backend.md`: run the same stack on plain **Docker Compose** and on
  **systemd** units, because a customer's platform team may standardise on Docker, Kubernetes,
  *or* direct host installs and the fleet should not force that choice. Include a
  `docker-compose.yml` under `services/` and sample unit files.

**Acceptance**
- `helm install` brings all pods Ready; probes green.
- A pod-to-pod connection that isn't in an allow rule is refused (demonstrated with a test).
- The Compose/systemd path starts the same services locally.

---

## Phase 3 — The Go notification bridge  *(Weekend 2, parallelizable)*  → closes Gap 5

Rewrite the smallest service — the ntfy/Telegram notification bridge — in Go.

**Scope (`services/notify-bridge-go/`)**
- Clean HTTP server exposing `/healthz`, `/readyz`, and a `/notify` endpoint.
- **Goroutines for fan-out** to multiple targets (ntfy + Telegram) concurrently.
- **`context` cancellation** and per-request timeouts on outbound calls.
- A **clean, reused `http.Client`** with sane timeouts (not `http.DefaultClient`).
- HMAC verification of inbound requests using the key from Secrets Manager.
- Table-driven unit tests; `Dockerfile` (distroless/static, non-root).

**Claim to substantiate**
> "I ported one production service to Go; here is the diff in operational behavior I
> measured." — capture that diff in `services/notify-bridge-go/NOTES.md`
> (startup time, memory footprint, image size, concurrency behavior vs. the original).

**Acceptance**
- `go test ./...` green; image builds; runs under Compose and on the cluster.
- `NOTES.md` documents concrete before/after operational differences.

---

## Phase 4 — CI/CD with an approval gate  *(Weekend 2–3)*  → closes Gap 3

Pipeline: **unit tests → container build → push to ECR → `helm upgrade`**, with a manual
**approval environment gate** before deploy (propose-then-approve applied to CI/CD).

**`.github/workflows/`**
- `ci.yml` — on PR: lint + unit tests for each service (matrix), Terraform `fmt`/`validate`,
  Helm `lint`.
- `cd.yml` — on merge to `main`: build + push images to ECR (OIDC auth to AWS, no static
  keys), then a job targeting a **GitHub Environment with required reviewers** that runs
  `helm upgrade --install` against the cluster only after approval.
- Auth via **GitHub OIDC → AWS IAM role** (documented in Terraform; no long-lived secrets).

**Talking point:** the approval gate is the same propose-then-approve trust pattern used in
the agent governance layer, now applied to deployments.

**Acceptance**
- A merge builds and pushes, then *waits* for approval; approving completes the rollout;
  rejecting leaves prod untouched.

---

## Phase 5 — SOC 2 mapping + the runbook  *(Weekend 3)*  → closes Gap 4 + the FDE artifact

**Compliance (`compliance/soc2-control-mapping.md`)**
- Read a SOC 2 **Type II** primer first so the language is correct (Trust Services Criteria,
  control vs. criterion, complementary user-entity controls).
- Table mapping each existing control to the TSC it supports:

  | Control | Supports (TSC) |
  |---|---|
  | Append-only audit stream | CC7.2/CC7.3 (monitoring), A1 partially |
  | One-shot action tokens | CC6.1 (logical access), CC6.6 |
  | Default-deny trust ladder | CC6.1, CC6.3 |
  | Network isolation (default-deny NetworkPolicy) | CC6.6, CC6.7 |
  | Secret rotation (Secrets Manager) | CC6.1, CC6.7 |

  (Refined and expanded in the file with plain-English "how this control is implemented here"
  notes and evidence pointers.)

**Runbook (`runbook/`) — the handover artifact**
- `01-prerequisites.md` — accounts, tools, IAM bootstrap, cost warning.
- `02-install.md` — zero → running fleet, targeting **< 1 hour**, copy-pasteable.
- `03-upgrade.md` — image bump, `helm upgrade`, migration notes.
- `04-failure-modes.md` — pod crashloop, image pull, IRSA/secret failures, NetworkPolicy
  lockout, node pressure — symptom → diagnosis → fix.
- `05-rollback.md` — `helm rollback`, image pinning, Terraform state recovery.
- `06-security-review-faq.md` — the questions an enterprise security team asks (data
  residency, secret handling, network egress, audit/evidence, blast radius, supply chain) with
  straight answers that point back to the code.

**Acceptance**
- A person who has never seen the repo can follow `02-install.md` to a running fleet in < 1 hr.
- Security FAQ answers every question with a pointer to where it's enforced in the repo.

---

## Phase 6 — End-to-end validation  *(Weekend 3)*

- **Clean-room test:** fresh AWS account (or fresh region/role), follow the runbook verbatim,
  time it, fix every place the docs lied. Repeat until < 1 hr.
- **One real ticket, end to end:** create a ticket → scheduler picks it up → ticket-to-pr
  runner opens a real PR on GitHub → notify-bridge fans out the notification. Capture the run
  (asciinema/screenshots) in `runbook/`.
- **Teardown proof:** `terraform destroy` + confirm no billable residue.

**Acceptance:** both "Done when" criteria demonstrably met; evidence linked in the runbook.

---

## What I can build now vs. what needs your environment

| Buildable now (no creds) | Needs your AWS account / secrets |
|---|---|
| All Terraform, Helm, NetworkPolicies | `terraform apply` against real AWS |
| Go notification bridge + tests | Real Secrets Manager values (HMAC keys, tokens) |
| GitHub Actions workflows | GitHub↔AWS OIDC trust + Environment reviewers |
| Reference services (option B) | Real ticket source / GitHub PR target |
| SOC 2 mapping + full runbook text | The timed clean-room run + real ticket E2E |

## Sequenced checklist

1. [x] Phase 0 — scaffold + defaulted to (B) reference stand-ins for existing services
2. [x] Phase 1 — Terraform: VPC → EKS → IRSA → ECR → Secrets Manager → GitHub OIDC *(CI-validated; needs live `apply`)*
3. [x] Phase 2 — Helm chart (probes/limits/hardening), default-deny NetworkPolicy, direct-backend docs
4. [x] Phase 3 — Go notification bridge + tests + operational-diff notes; 3 reference services
5. [x] Phase 4 — CI/CD with OIDC + approval gate
6. [x] Phase 5 — SOC 2 mapping + full runbook (install/upgrade/failure/rollback/security-FAQ)
7. [~] Phase 6 — pipeline **proven locally** (`scripts/e2e_local.py` passes); timed clean-room
   install + real on-cluster PR + teardown proof need a live AWS account — see [`VALIDATION.md`](./VALIDATION.md)
