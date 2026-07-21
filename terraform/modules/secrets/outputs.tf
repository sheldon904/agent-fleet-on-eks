output "secret_arns" {
  description = "Map of secret name => ARN (feed these to IRSA roles that need read access)."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}

output "secret_names" {
  description = "List of created secret names."
  value       = [for s in aws_secretsmanager_secret.this : s.name]
}
