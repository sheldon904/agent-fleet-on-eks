# 05 — Rollback & teardown

## Roll back a bad release

Helm keeps release history. To return to the previous revision:

```bash
helm -n agent-fleet history agent-fleet
helm -n agent-fleet rollback agent-fleet        # previous revision
helm -n agent-fleet rollback agent-fleet <REV>  # a specific revision
kubectl -n agent-fleet rollout status deploy
```

Because images are immutable and SHA-tagged, a rollback pulls the exact prior image — no
"latest moved under me" surprises.

## Roll back a single service

```bash
helm upgrade agent-fleet charts/agent-fleet -n agent-fleet --reuse-values \
  --set services.notify-bridge.tag=<previous-sha> --wait
```

## Roll back an infrastructure change

Terraform state is the source of truth. To undo an uncommitted change, revert the `.tf`
files (or `terraform.tfvars`) and `terraform apply`. For a change already applied that you want
gone, apply the prior configuration. If state is remote (S3), previous state versions are
retained (bucket versioning) for recovery.

> Note: some infra changes are destructive (e.g. changing the cluster name or subnet layout
> forces replacement). Read the plan carefully — Terraform marks replacements with `-/+`.

## Emergency: stop all agent activity now

Scale the scheduler to zero so no new tickets are dispatched (governance and audit stay up):

```bash
kubectl -n agent-fleet scale deploy/scheduler --replicas=0
```

## Full teardown

Do this at the end of every work session to stop billing.

```bash
# 1. remove the Helm release (optional; destroy removes the cluster anyway)
helm -n agent-fleet uninstall agent-fleet

# 2. destroy all AWS infrastructure
cd terraform/envs/dev
terraform destroy      # type yes
```

### Verify nothing billable remains

```bash
aws ec2 describe-nat-gateways --filter Name=state,Values=available
aws ec2 describe-addresses            # no orphaned Elastic IPs
aws elbv2 describe-load-balancers     # no leftover LBs
```

Secrets are force-deleted (`recovery_window_in_days = 0`) and ECR repos are `force_delete`, so
`terraform destroy` leaves nothing behind and you can recreate the same names immediately.

Next: [06 — Security review FAQ](./06-security-review-faq.md)
