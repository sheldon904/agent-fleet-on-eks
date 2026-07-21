# terraform/ — cloud foundation (Gap 2)

Minimal-but-real AWS footprint that stands up and tears down cleanly. Closes gap 2 of
[`../PLAN.md`](../PLAN.md#phase-1--terraform-foundation-weekend-1-the-bulk).

## Layout

```
terraform/
├── bootstrap/            # one-time: S3 state bucket + DynamoDB lock table (optional)
├── modules/
│   ├── vpc/              # curated wrapper: VPC, 2 AZs, public+private subnets, 1 NAT
│   ├── eks/              # curated wrapper: cluster + one managed node group, IRSA/OIDC
│   ├── irsa/             # raw: one least-privilege IAM role per ServiceAccount
│   ├── ecr/              # raw: one repo per service + scan-on-push + lifecycle policy
│   └── secrets/          # raw: Secrets Manager entries (values injected out-of-band)
└── envs/
    └── dev/              # root module wiring it all together
        ├── main.tf  variables.tf  outputs.tf  versions.tf
        ├── terraform.tfvars.example
        └── backend.hcl.example
```

## Version pins

| Component | Pin | Note |
|---|---|---|
| Terraform | `>= 1.5.0` | |
| AWS provider | `>= 5.80, < 6.0` | |
| VPC module | `~> 5.8` | |
| EKS module | `~> 20.31` | access-entry auth; IRSA/OIDC managed for us |

Upgrade path to EKS module v21 / AWS provider 6 is noted in `modules/eks/main.tf`.

## Prerequisites

- AWS credentials with admin-ish permissions (`aws sts get-caller-identity` works)
- `terraform >= 1.5`, `aws` CLI v2, `kubectl`
- **Read the cost table in [`../README.md`](../README.md#cost-read-before-terraform-apply). Tear down between sessions.**

## Quickstart (local state)

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars   # edit: region, cluster_version, cost knobs

terraform init
terraform apply                                 # ~15-20 min (EKS control plane is the wait)

# Point kubectl at the cluster (command is also a terraform output)
eval "$(terraform output -raw configure_kubectl)"
kubectl get nodes                               # nodes should reach Ready
```

`terraform apply` sets `cluster_version = "1.32"` by default — **change it to a version EKS
currently supports** at apply time or the create will fail.

## Tear down (do this every session)

```bash
cd terraform/envs/dev
terraform destroy
```

Secrets are force-deleted (`recovery_window_in_days = 0`) and ECR repos are `force_delete`, so
destroy is clean and you can recreate the same names immediately. Verify nothing billable
lingers (no orphaned NAT/EIP/ENI/LB) in the console or Cost Explorer.

## Remote state (teams, optional)

```bash
cd terraform/bootstrap
terraform init && terraform apply \
  -var state_bucket_name=YOURNAME-agent-fleet-tfstate
terraform output backend_hcl        # copy into ../envs/dev/backend.hcl

cd ../envs/dev
cp backend.hcl.example backend.hcl  # paste the values
# uncomment the backend "s3" block in versions.tf, then:
terraform init -backend-config=backend.hcl -migrate-state
```

## What Phase 1 produces (and what it intentionally leaves to later phases)

- **Produces:** VPC, EKS cluster + node group, IRSA roles per workload, ECR repos, Secrets
  Manager entries, and the outputs (`ecr_repository_urls`, `irsa_role_arns`, `secret_arns`)
  that Phase 2's Helm charts consume.
- **Left to Phase 2:** installing the AWS Secrets Store CSI driver, the Helm releases, and the
  default-deny NetworkPolicy. Terraform here stays AWS-only and does not touch the cluster's
  workloads, so infra and app lifecycles stay decoupled.

## Key design decisions

- **Private subnets for nodes**; workloads reach AWS via **IRSA**, never node instance-profile
  credentials. Each IRSA role can read only its own secret.
- **One NAT gateway** in dev (`single_nat_gateway = true`) to save ~$66/mo; flip to `false`
  for one-per-AZ HA.
- **Immutable ECR tags** paired with SHA-based CI tags; lifecycle policy keeps ≤30 images and
  expires untagged after 14 days.
- **No secret values in Git or state:** Terraform creates the secret container with a
  placeholder and `ignore_changes`; operators set real values with `aws secretsmanager
  put-secret-value`.
