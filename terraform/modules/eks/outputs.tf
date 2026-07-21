output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 CA data for the cluster (for kubeconfig)."
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_version" {
  description = "Kubernetes version running on the cluster."
  value       = module.eks.cluster_version
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN — used by IRSA roles' trust policies."
  value       = module.eks.oidc_provider_arn
}

output "oidc_provider" {
  description = "OIDC issuer host/path without the https:// prefix — used in IRSA sub/aud conditions."
  value       = replace(module.eks.cluster_oidc_issuer_url, "https://", "")
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the control plane."
  value       = module.eks.cluster_security_group_id
}

output "node_security_group_id" {
  description = "Security group ID attached to the managed nodes."
  value       = module.eks.node_security_group_id
}
