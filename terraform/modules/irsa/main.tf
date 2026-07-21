# modules/irsa — one least-privilege IAM role bound to a single Kubernetes ServiceAccount
# via the cluster's OIDC provider (IAM Roles for Service Accounts). No node-wide creds.
#
# The role is assumable ONLY by the exact namespace/service-account pair, and (optionally)
# granted read access to a specific set of Secrets Manager secret ARNs — nothing more.

data "aws_iam_policy_document" "assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    # Bind to exactly this ServiceAccount.
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account}"]
    }

    # Audience must be the STS service.
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name                 = var.role_name
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = 3600
  tags                 = var.tags
}

# Scoped read access to just this workload's secrets.
data "aws_iam_policy_document" "secrets" {
  count = length(var.secret_arns) > 0 ? 1 : 0

  statement {
    sid       = "ReadOwnSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = var.secret_arns
  }
}

resource "aws_iam_role_policy" "secrets" {
  count  = length(var.secret_arns) > 0 ? 1 : 0
  name   = "${var.role_name}-secrets-read"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.secrets[0].json
}
