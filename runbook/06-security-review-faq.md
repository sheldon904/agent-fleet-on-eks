# 06 — Security review FAQ

The questions an enterprise security team asks before letting an agent fleet run in their
account, with straight answers and a pointer to where each is enforced.

## Data & tenancy

**Where does our data live? Does anything leave our account?**
Everything runs in *your* AWS account and cluster. The only outbound calls are the ones you
configure: the runner to the GitHub API, and the notify-bridge to your ntfy/Telegram endpoints.
The default-deny NetworkPolicy blocks all other egress (`charts/agent-fleet/templates/networkpolicy.yaml`).

**Is it multi-tenant?**
No. It's a single-tenant deployment you own end to end. Isolation is per-namespace with network
policies; run separate clusters/namespaces for separate trust domains.

## Secrets

**How are secrets stored and delivered?**
In AWS Secrets Manager, delivered to pods as files via the Secrets Store CSI driver — never in
container images, environment variables baked into manifests, Git, or etcd. Terraform creates
the secret containers with placeholders and `ignore_changes`, so real values are set
out-of-band and never enter state (`terraform/modules/secrets`).

**Can one workload read another's secrets?**
No. Each workload has its own IRSA role scoped to only the secret ARNs it needs
(`terraform/modules/irsa`, `envs/dev` `module.irsa`). The scheduler has no AWS credentials at all.

**How is rotation handled?**
`aws secretsmanager put-secret-value` + the CSI driver's rotation poll; force with a
`rollout restart`. Rotation cadence is a customer-owned control (see the SOC 2 CUECs).

## Access & authorization

**What stops the agent from doing something it shouldn't?**
Two layers. (1) A **default-deny trust ladder**: a caller can only request the actions
explicitly granted to it; the scheduler may request `open_pr` and nothing else
(`services/governance-mcp`). (2) **One-shot, HMAC-signed, time-bounded action tokens**: the
runner re-verifies and consumes the token before acting, and a replay is rejected and logged.

**How do humans stay in the loop?**
Deploys are gated on a required reviewer in the GitHub `production` environment
(`.github/workflows/cd.yml`) — the same propose-then-approve pattern the agents use internally.

**How does CI authenticate to AWS?**
GitHub OIDC → a scoped IAM role, with the trust policy pinned to your specific repo. **No
long-lived AWS keys** are stored in GitHub (`terraform/modules/github-oidc`).

## Network

**What's the blast radius if a pod is compromised?**
Bounded by the NetworkPolicies: a compromised pod can only reach the exact peers/ports in its
allow rule, and only the internet destinations it's explicitly granted (runner → GitHub:443,
notify-bridge → ntfy/Telegram:443). Nodes are in private subnets with no public IPs; the
Kubernetes API endpoint can be restricted to known CIDRs (`endpoint_public_access_cidrs`).

**Is pod-to-pod traffic authenticated?**
Requests that carry authority (notify) are HMAC-signed and verified. For full mTLS between
services, add a service mesh — out of scope for this reference but compatible.

## Auditability

**What's the evidence trail?**
An append-only, hash-chained audit stream: every governance decision (issue, consume, deny,
replay, invalid) is recorded with a hash that commits to the previous record, and mirrored to
stdout for your log pipeline (`services/governance-mcp`, `verify_chain`). Tampering with any
record breaks the chain and is detectable.

**How do we monitor it?**
Ship the governance stdout to your SIEM and alert on `token.denied` and `token.replay`. Both
indicate someone/something trying to exceed its authority.

## Supply chain

**Where do the images come from and how are they hardened?**
Built from this repo in your CI, pushed to your ECR with **scan-on-push** and **immutable
tags**. The Go bridge runs on `distroless/static:nonroot` (no shell, no libc); the Python
services run as a non-root user. All pods run with `readOnlyRootFilesystem`,
`allowPrivilegeEscalation: false`, and all Linux capabilities dropped
(`charts/agent-fleet/templates/deployment.yaml`).

**Third-party dependencies?**
The Go bridge and the reference services use **standard library only** — nothing to audit
beyond the language runtime. The Terraform uses the well-known community VPC/EKS modules,
pinned by version.

## Availability

**What happens if a node or pod dies?**
Managed node group autoscaling (1–3) plus liveness/readiness probes reschedule and restart
workloads. Resource requests/limits keep one service from starving another. For production,
switch to one-NAT-per-AZ (`single_nat_gateway = false`) and raise replica counts.

## Compliance

**Do you have a control mapping?**
Yes — [`compliance/soc2-control-mapping.md`](../compliance/soc2-control-mapping.md) maps each
control to the SOC 2 Trust Services Criteria it supports, with the evidence an auditor would
sample and the controls the customer must own (CUECs).

← Back to [runbook index](./README.md) · Also: [direct-backend](./direct-backend.md)
