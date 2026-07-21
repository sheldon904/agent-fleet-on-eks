# runbook/ — the customer-facing deployment runbook (the FDE artifact)

Written for a **customer's platform engineer**, not for us. This is the reusable-pattern
reference a platform team is handed at the end of an engagement. See
[`../PLAN.md`](../PLAN.md#phase-5--soc-2-mapping--the-runbook-weekend-3-closes-gap-4--the-fde-artifact)
Phase 5.

## Pages

| File | Contents |
|------|----------|
| [`01-prerequisites.md`](./01-prerequisites.md) | Accounts, tools, IAM bootstrap, **cost warning** |
| [`02-install.md`](./02-install.md) | Zero → running fleet, copy-pasteable, target **< 1 hour** |
| [`03-upgrade.md`](./03-upgrade.md) | Image bump, `helm upgrade`, migration notes |
| [`04-failure-modes.md`](./04-failure-modes.md) | Crashloop, image pull, IRSA/secret failures, NetworkPolicy lockout, node pressure — symptom → diagnosis → fix |
| [`05-rollback.md`](./05-rollback.md) | `helm rollback`, image pinning, Terraform state recovery |
| [`06-security-review-faq.md`](./06-security-review-faq.md) | The questions an enterprise security team asks, with answers pointing back into the repo |
| [`direct-backend.md`](./direct-backend.md) | Running the same stack on plain **Docker Compose / systemd** , for platform teams not standardised on Kubernetes |

## Bar to clear

- Someone who has never seen this repo follows `02-install.md` to a running fleet in **< 1 hr**.
- `06-security-review-faq.md` answers every question with a pointer to where it's enforced.
- Evidence from the timed clean-room run and the one real on-cluster ticket gets linked here
  once run against a live AWS account (see [`../VALIDATION.md`](../VALIDATION.md)).
