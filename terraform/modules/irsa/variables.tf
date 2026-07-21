variable "role_name" {
  description = "Name of the IAM role."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the cluster's IAM OIDC provider (from the eks module)."
  type        = string
}

variable "oidc_provider" {
  description = "OIDC issuer host/path without https:// (from the eks module)."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace of the ServiceAccount."
  type        = string
}

variable "service_account" {
  description = "Kubernetes ServiceAccount name allowed to assume this role."
  type        = string
}

variable "secret_arns" {
  description = "Secrets Manager secret ARNs this role may read. Empty for no secret access."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to the role."
  type        = map(string)
  default     = {}
}
