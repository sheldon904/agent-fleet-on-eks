# 03 — Upgrade

## Ship a new version of a service

Images are tagged by commit SHA (immutable). To roll out a new build:

```bash
TAG=$(git rev-parse --short=12 HEAD)
docker build -t "$REGISTRY/agent-fleet/notify-bridge:$TAG" services/notify-bridge-go
docker push  "$REGISTRY/agent-fleet/notify-bridge:$TAG"

helm upgrade agent-fleet charts/agent-fleet -n agent-fleet --reuse-values \
  --set services.notify-bridge.tag="$TAG" --wait --timeout 5m
```

`--wait` blocks until the new pods are Ready; if they never become Ready, Helm reports failure
and you can [roll back](./05-rollback.md). Through CI/CD this is automatic on merge to `main`,
behind the approval gate.

## Turn on real GitHub PRs

```bash
# store a GitHub token the runner can read (add a secret + grant its IRSA role read access first)
helm upgrade agent-fleet charts/agent-fleet -n agent-fleet --reuse-values \
  --set services.ticket-to-pr-runner.env.DRY_RUN=false \
  --set services.ticket-to-pr-runner.env.GITHUB_REPO=OWNER/REPO
```

The runner reads `GITHUB_TOKEN` (or `GITHUB_TOKEN_FILE` from a CSI-mounted secret). Scope the
token to the target repo only.

## Change a config value (e.g. the trust ladder)

```bash
helm upgrade agent-fleet charts/agent-fleet -n agent-fleet --reuse-values \
  --set-string services.governance-mcp.env.TRUST_LADDER='{"scheduler":["open_pr"]}'
```

## Upgrade the Kubernetes version

Bump one minor version at a time. Update `cluster_version` in `terraform.tfvars`, then:

```bash
cd terraform/envs/dev
terraform apply     # updates the control plane, then the managed node group
```

Managed node groups roll nodes automatically. Watch `kubectl get nodes` and confirm pods
reschedule. Upgrade cluster add-ons (coredns, kube-proxy, vpc-cni) in the same apply — the eks
module tracks compatible versions.

## Rotate a secret

```bash
aws secretsmanager put-secret-value --secret-id agent-fleet/notify-hmac \
  --secret-string "$(openssl rand -hex 32)"
```

With `enableSecretRotation=true` on the CSI driver, mounted files refresh on the driver's
rotation-poll interval. To force it immediately, restart the consumers:

```bash
kubectl -n agent-fleet rollout restart deploy/notify-bridge deploy/ticket-to-pr-runner
```

Rotate `notify-hmac` for both consumers together so signatures keep matching.

Next: [04 — Failure modes](./04-failure-modes.md)
