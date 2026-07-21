output "role_arn" {
  description = "ARN of the IRSA role. Annotate the ServiceAccount with eks.amazonaws.com/role-arn = this."
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Name of the IRSA role."
  value       = aws_iam_role.this.name
}
