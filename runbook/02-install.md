# 02 — Install: fresh AWS account → running fleet in under an hour

Every command is copy-pasteable. Set these once:

```bash
export AWS_REGION=us-east-1
export CLUSTER=agent-fleet
```

## 1. Provision infrastructure (Terraform) — ~15–20 min

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set cluster_version to a currently-supported EKS version.
# For CI/CD later, also add:  github_repo = "OWNER/REPO"

terraform init
terraform apply    # review the plan, type yes
```

This creates the VPC (private subnets, 1 NAT), the EKS cluster + node group, IRSA roles per
workload, ECR repos, and Secrets Manager entries. Capture the outputs:

```bash
terraform output
export REGISTRY=$(terraform output -raw ecr_registry)
eval "$(terraform output -raw configure_kubectl)"   # points kubectl at the cluster
kubectl get nodes                                    # wait for Ready
```

## 2. Install the Secrets Store CSI driver + AWS provider — ~2 min

The workloads read secrets from files mounted by this driver (kept out of etcd).

```bash
helm repo add secrets-store-csi-driver https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts
helm repo update
helm install csi-secrets-store secrets-store-csi-driver/secrets-store-csi-driver \
  -n kube-system --set syncSecret.enabled=false --set enableSecretRotation=true

kubectl apply -f https://raw.githubusercontent.com/aws/secrets-store-csi-driver-provider-aws/main/deployment/aws-provider-installer.yaml
```

## 3. Set the real secret values — ~1 min

Terraform created the secret containers with placeholders; put real keys in them. The runner
and the notify-bridge must share `notify-hmac`.

```bash
aws secretsmanager put-secret-value --region "$AWS_REGION" \
  --secret-id agent-fleet/governance-mcp --secret-string "$(openssl rand -hex 32)"
aws secretsmanager put-secret-value --region "$AWS_REGION" \
  --secret-id agent-fleet/notify-hmac    --secret-string "$(openssl rand -hex 32)"
```

## 4. Build & push the images — ~5 min

(Or let CI do it — see [.github/README](../.github/README.md). Manual path:)

```bash
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"

for s in governance-mcp scheduler ticket-to-pr-runner; do
  docker build -t "$REGISTRY/agent-fleet/$s:v1" "services/$s"
  docker push "$REGISTRY/agent-fleet/$s:v1"
done
docker build -t "$REGISTRY/agent-fleet/notify-bridge:v1" services/notify-bridge-go
docker push "$REGISTRY/agent-fleet/notify-bridge:v1"
```

## 5. Deploy the fleet (Helm) — ~2 min

```bash
cd ../../..   # repo root
cp deploy/values.production.yaml.example deploy/values.production.yaml
# fill in the IRSA role ARNs:
terraform -chdir=terraform/envs/dev output irsa_role_arns

helm upgrade --install agent-fleet charts/agent-fleet \
  -n agent-fleet --create-namespace \
  --set image.registry="$REGISTRY" \
  --set services.governance-mcp.tag=v1 \
  --set services.scheduler.tag=v1 \
  --set services.ticket-to-pr-runner.tag=v1 \
  --set services.notify-bridge.tag=v1 \
  -f deploy/values.production.yaml

kubectl -n agent-fleet get pods            # all should reach Running/Ready
kubectl -n agent-fleet get networkpolicy   # default-deny + allow rules
```

## 6. Run one ticket end to end

```bash
kubectl -n agent-fleet port-forward svc/scheduler 8083:8080 >/dev/null 2>&1 &
curl -sS -XPOST localhost:8083/enqueue -d '{"id":"TCK-1","title":"add healthcheck","body":"probe /healthz"}'

# within POLL_INTERVAL seconds:
kubectl -n agent-fleet logs deploy/governance-mcp | tail    # token.issued then token.consumed
kubectl -n agent-fleet get svc/scheduler                    # /status shows the processed result
```

You now have the whole trust flow running: scheduler → governance token → runner → PR →
signed notification, every step on the audit stream.

To open a **real GitHub PR**, set `DRY_RUN=false`, provide a `GITHUB_TOKEN`/`GITHUB_REPO`, and
redeploy — see [03-upgrade](./03-upgrade.md).

## 7. When you're done

```bash
cd terraform/envs/dev && terraform destroy
```

Next: [03 — Upgrade](./03-upgrade.md) · [04 — Failure modes](./04-failure-modes.md)
