variable "github_repo" {
  description = "GitHub repo allowed to assume the role, as owner/name."
  type        = string
}

variable "role_name" {
  description = "Name of the CI IAM role."
  type        = string
}

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}

variable "ecr_repository_arns" {
  description = "ECR repository ARNs the CI role may push/pull."
  type        = list(string)
}

variable "cluster_arn" {
  description = "EKS cluster ARN the CI role may describe."
  type        = string
}

variable "tags" {
  description = "Tags applied to the role and provider."
  type        = map(string)
  default     = {}
}
