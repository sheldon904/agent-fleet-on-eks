# .github/ — CI/CD (Gap 3)

**test → build → push to ECR → (approval gate) → `helm upgrade`**, with GitHub OIDC → AWS
(no long-lived keys). See [`../PLAN.md`](../PLAN.md#phase-4--cicd-with-an-approval-gate-weekend-23) Phase 4.

## Workflows

| File | Trigger | Does |
|------|---------|------|
| `workflows/ci.yml` | PR + push | Go test/vet/build, Python unit tests (matrix), the local e2e pipeline, `terraform fmt`+`validate`, `helm lint`+`template`+`kubeconform` |
| `workflows/cd.yml` | push to `main` | build+push all images to ECR, then an **approval-gated** `helm upgrade` |

## The approval gate

The `deploy` job sets `environment: production`. Configure **Required reviewers** on that
GitHub Environment (Settings → Environments → production) and the rollout pauses until a human
approves — the same propose-then-approve trust pattern the fleet's governance layer uses,
applied to CD.

## One-time setup

1. `terraform apply` with `-var github_repo=OWNER/REPO` creates the OIDC provider + CI role.
2. Set repo **variable** `AWS_DEPLOY_ROLE_ARN` to the `ci_deploy_role_arn` Terraform output.
3. Create the `production` Environment with required reviewers.
4. Copy `deploy/values.production.yaml.example` → `deploy/values.production.yaml` and fill in
   the IRSA role ARNs from `terraform output irsa_role_arns`.

No AWS access keys are ever stored in GitHub.
