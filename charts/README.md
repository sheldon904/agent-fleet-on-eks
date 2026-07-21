# charts/ — Kubernetes workloads (Gap 1)

One values-driven Helm chart, `agent-fleet/`, renders every service. See
[`../PLAN.md`](../PLAN.md#phase-2--workloads-helm--k8s-hardening-weekend-2) Phase 2.

## Why one chart, not four

The four services differ only in config, so a single chart with a `services` map beats four
near-identical charts: one place to change a probe or a security context, and every service
inherits it. That *is* the reusable pattern — adding a fifth service is a values entry, not a
new chart.

## Layout

```
charts/agent-fleet/
├── Chart.yaml
├── values.yaml            # the services map: images, env, secrets, IRSA, network rules
└── templates/
    ├── deployment.yaml         # probes, resource limits, non-root, read-only rootfs, drop ALL caps
    ├── service.yaml
    ├── serviceaccount.yaml      # IRSA annotation per service
    ├── secretproviderclass.yaml # AWS Secrets Store CSI objects
    ├── networkpolicy.yaml       # default-deny + explicit allow rules
    └── NOTES.txt
```

## Every workload ships

- Liveness (`/healthz`) + readiness (`/readyz`) probes, `resources.requests/limits`.
- `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, all caps dropped,
  `seccompProfile: RuntimeDefault`.
- A ServiceAccount annotated for **IRSA** (from the Terraform `irsa_role_arns` output).
- Secrets via the **AWS Secrets Store CSI driver**, mounted as files under `/secrets` (kept out
  of etcd); the app reads them through `*_FILE` env vars.

## Network isolation — the air-gap instinct in K8s

`templates/networkpolicy.yaml` renders a namespace-wide **default-deny** (ingress + egress),
a DNS-egress allowance, then one allow policy per service:

| Service | Ingress from | Egress to |
|---|---|---|
| governance-mcp | scheduler, ticket-to-pr-runner | (none — DNS only) |
| scheduler | (port-forward) | governance-mcp, ticket-to-pr-runner |
| ticket-to-pr-runner | scheduler | governance-mcp, notify-bridge, internet:443 (GitHub) |
| notify-bridge | ticket-to-pr-runner | internet:443 (ntfy/Telegram) |

Everything else is denied.

## Install

Prerequisite: the **AWS Secrets Store CSI driver + AWS provider** installed in the cluster
(see the runbook). Then:

```bash
helm upgrade --install agent-fleet charts/agent-fleet \
  -n agent-fleet --create-namespace \
  --set image.registry=$(terraform -chdir=terraform/envs/dev output -raw ecr_registry 2>/dev/null || echo "") \
  -f my-values.yaml   # sets image tags + irsaRoleArn per service from terraform outputs

kubectl -n agent-fleet get pods
```

## Validate the chart locally

```bash
helm lint charts/agent-fleet
helm template agent-fleet charts/agent-fleet -n agent-fleet | kubectl apply --dry-run=client -f -
```

CI runs `helm lint` + `helm template` on every PR.
