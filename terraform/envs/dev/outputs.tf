output "region" {
  description = "AWS region the fleet is deployed in."
  value       = var.region
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "ecr_repository_urls" {
  description = "ECR repository URLs (push/pull targets for CI), keyed by repo name."
  value       = module.ecr.repository_urls
}

output "secret_arns" {
  description = "Secrets Manager ARNs, keyed by secret name."
  value       = module.secrets.secret_arns
}

output "irsa_role_arns" {
  description = "IRSA role ARNs, keyed by ServiceAccount name (annotate SAs with these)."
  value       = { for k, m in module.irsa : k => m.role_arn }
}

output "oidc_provider_arn" {
  description = "Cluster IAM OIDC provider ARN."
  value       = module.eks.oidc_provider_arn
}

output "ecr_registry" {
  description = "ECR registry host (derive from any repo URL). Empty if no repos."
  value       = length(module.ecr.repository_urls) > 0 ? split("/", values(module.ecr.repository_urls)[0])[0] : ""
}

output "ci_deploy_role_arn" {
  description = "CI deploy role ARN — set as the GitHub repo variable AWS_DEPLOY_ROLE_ARN."
  value       = var.github_repo != "" ? module.github_oidc[0].role_arn : ""
}
