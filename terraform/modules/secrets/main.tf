# modules/secrets — Secrets Manager entries for the HMAC keys and API tokens that were
# previously in env vars. Terraform creates the *container*; real values are injected
# out-of-band and never committed (see the placeholder + ignore_changes below).

resource "aws_secretsmanager_secret" "this" {
  for_each = toset(var.secret_names)

  name        = each.value
  description = "agent-fleet secret: ${each.value}"

  # recovery_window_in_days = 0 force-deletes on destroy so dev clusters tear down clean and
  # the same name can be recreated immediately. Use 7-30 in production for accidental-delete
  # protection.
  recovery_window_in_days = var.recovery_window_in_days

  tags = var.tags
}

# Seed a placeholder so the secret is resolvable before an operator sets the real value.
# ignore_changes means Terraform never clobbers a value set out-of-band via:
#   aws secretsmanager put-secret-value --secret-id <name> --secret-string '<real value>'
resource "aws_secretsmanager_secret_version" "placeholder" {
  for_each  = aws_secretsmanager_secret.this
  secret_id = each.value.id

  secret_string = jsonencode({ placeholder = "set-out-of-band" })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
