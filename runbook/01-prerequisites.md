# 01 — Prerequisites

Read this once before you start. Total setup time from here to a running fleet is **under an
hour** ([02-install](./02-install.md)); most of it is the EKS control plane provisioning while
you do nothing.

## Accounts & access

- An **AWS account** you can create infrastructure in. The identity you run Terraform as needs
  permissions for VPC, EKS, EC2, IAM, ECR, and Secrets Manager (an admin or
  power-user role is simplest for a demo account).
- Confirm it works: `aws sts get-caller-identity`.
- (Optional, for CI/CD and real PRs) a **GitHub repo** and a token with `repo` scope.

## Tools

| Tool | Version | Check |
|------|---------|-------|
| Terraform | ≥ 1.5 | `terraform version` |
| AWS CLI | v2 | `aws --version` |
| kubectl | ≥ 1.29 | `kubectl version --client` |
| Helm | ≥ 3.12 | `helm version` |
| Docker | any recent | `docker version` |
| Go | 1.26.10+ (only to build/test the bridge locally) | `go version` |

## Cost — read this

A running cluster is **~$180–200/month** if left on 24×7; a single ~8-hour work session that
you tear down afterward is **≈ $3–5**. The dominant costs are the EKS control plane
(~$0.10/hr), two `t3.medium` nodes, and one NAT gateway. See the table in the
[top-level README](../README.md#cost-read-before-terraform-apply).

**Always `terraform destroy` when you finish a session.** [05-rollback](./05-rollback.md#full-teardown)
has the teardown checklist.

## Get the repo

```bash
git clone https://github.com/sheldon904/agent-fleet-on-eks.git
cd agent-fleet-on-eks
```

## Decide two things now

1. **Region** — default `us-east-1`. Set it consistently in `terraform.tfvars` and your AWS CLI.
2. **Kubernetes version** — `terraform/envs/dev/variables.tf` defaults `cluster_version` to a
   pinned value. Set it to a version **EKS currently supports** (`aws eks
   describe-cluster-versions` or the EKS docs) or `terraform apply` will fail at cluster create.

Next: [02 — Install](./02-install.md).
