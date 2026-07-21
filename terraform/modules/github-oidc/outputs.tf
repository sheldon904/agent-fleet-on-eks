output "role_arn" {
  description = "ARN of the CI role. Set this as the GitHub repo variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.ci.arn
}

output "role_name" {
  description = "Name of the CI role (for the EKS access entry)."
  value       = aws_iam_role.ci.name
}
