# 04 — Failure modes

Symptom → diagnosis → fix. Start every investigation with:

```bash
kubectl -n agent-fleet get pods
kubectl -n agent-fleet describe pod <pod>
kubectl -n agent-fleet logs <pod> [-p]      # -p for the previous (crashed) container
```

## Pod stuck `CrashLoopBackOff`

- **notify-bridge exits immediately** → it requires an HMAC secret. Confirm the CSI mount:
  `kubectl -n agent-fleet exec deploy/notify-bridge -- ls /secrets` should show `hmac`.
  If empty, the secret isn't mounting — see *Secret not mounting* below.
- **Any service** → read the last log line; it's structured JSON with the reason.

## Pod stuck `ImagePullBackOff` / `ErrImagePull`

- Wrong registry/tag: `kubectl -n agent-fleet describe pod <pod>` shows the image ref.
  Confirm it matches `terraform output ecr_registry` and a pushed tag (`aws ecr
  list-images --repository-name agent-fleet/<service>`).
- Nodes can't reach ECR: check the node egress/NAT (private subnets route through the NAT
  gateway). `kubectl get nodes -o wide` and confirm the NAT exists in the VPC.

## Secret not mounting (pod `ContainerCreating`, events mention secrets-store)

```bash
kubectl -n agent-fleet describe pod <pod>       # look for CSI mount errors
kubectl -n kube-system get pods -l app=secrets-store-csi-driver
kubectl -n kube-system get pods -l app=secrets-store-csi-driver-provider-aws
```

Common causes:
- The **CSI driver or AWS provider isn't installed** ([02 step 2](./02-install.md#2-install-the-secrets-store-csi-driver--aws-provider--2-min)).
- **IRSA misconfigured**: the ServiceAccount lacks the role annotation, or the role can't read
  the secret. Check: `kubectl -n agent-fleet get sa <service> -o yaml` has
  `eks.amazonaws.com/role-arn`, and the role's policy lists the secret ARN.
- The **secret value was never set** (still the Terraform placeholder) — the mount still works,
  but the app behaves oddly. Set it ([02 step 3](./02-install.md#3-set-the-real-secret-values--1-min)).

## Pod `Running` but never `Ready`

Readiness probe failing. `notify-bridge` reports not-ready when **no notification target is
configured** — set `NTFY_URL`+`NTFY_TOPIC` or Telegram vars. For others, `kubectl logs` shows
request lines; hit the probe directly:

```bash
kubectl -n agent-fleet exec deploy/<svc> -- python -c \
  "import urllib.request;print(urllib.request.urlopen('http://localhost:8080/readyz').read())"
```

## A service can't reach another (timeouts between pods)

Almost always the **NetworkPolicy**. The design is default-deny; a new call path needs an
explicit allow rule.

```bash
kubectl -n agent-fleet get networkpolicy
kubectl -n agent-fleet describe networkpolicy allow-<service>
```

Add the source to that service's `network.ingressFrom` (and the caller's `egressToServices`)
in `values.yaml`, then `helm upgrade`. To confirm a policy is the cause, temporarily test from
an allowed pod vs. a disallowed one.

## `token.denied` / `token.replay` in the governance logs

- **denied** → the caller isn't on the trust ladder for that action. Expected for anything but
  the scheduler requesting `open_pr`. If a legitimate caller is denied, update `TRUST_LADDER`.
- **replay** → a one-shot token was used twice. Expected to be rejected; if it happens in normal
  flow, something is retrying a consumed token — check the scheduler/runner for double-dispatch.

## Node pressure / pods `Pending`

```bash
kubectl -n agent-fleet describe pod <pending-pod>   # "Insufficient cpu/memory"?
kubectl top nodes
```

The node group autoscales 1–3. Raise `node_desired_size`/`node_max_size` (or node size) in
`terraform.tfvars` and `terraform apply`, or lower the services' resource requests.

## CI/CD deploy stuck

- **Waiting at approval** → expected; approve the `production` environment in GitHub.
- **OIDC auth fails** → confirm the repo variable `AWS_DEPLOY_ROLE_ARN` and that `github_repo`
  in Terraform matches `owner/name` exactly (the role's trust policy pins the repo).
- **helm upgrade fails on RBAC** → the CI role needs the EKS access entry (created when
  `github_repo` is set). Confirm with `aws eks list-access-entries --cluster-name agent-fleet`.

Next: [05 — Rollback](./05-rollback.md)
