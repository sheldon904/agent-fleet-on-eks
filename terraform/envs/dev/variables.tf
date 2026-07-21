variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Cluster/name prefix for all fleet resources."
  type        = string
  default     = "agent-fleet"
}

variable "cluster_version" {
  description = <<-EOT
    Kubernetes version for EKS. MUST be a version EKS currently supports when you apply.
    Check `aws eks describe-cluster-versions` (or the EKS docs) and set accordingly.
  EOT
  type        = string
  default     = "1.32"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "AZs to use. Empty = first two available in the region."
  type        = list(string)
  default     = []
}

variable "private_subnets" {
  description = "Private subnet CIDRs (one per AZ). Must match the number of AZs."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDRs (one per AZ). Must match the number of AZs."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "single_nat_gateway" {
  description = "One NAT gateway for all AZs (cheaper dev default). False = one per AZ (HA)."
  type        = bool
  default     = true
}

variable "node_instance_types" {
  description = "Managed node group instance types."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min_size" {
  description = "Minimum nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum nodes."
  type        = number
  default     = 3
}

variable "node_desired_size" {
  description = "Desired nodes."
  type        = number
  default     = 2
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API publicly (handy for a demo cluster)."
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint. Restrict in production."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "services" {
  description = "Fleet services. Each gets an ECR repository."
  type        = list(string)
  default     = ["governance-mcp", "scheduler", "ticket-to-pr-runner", "notify-bridge"]
}

variable "secrets" {
  description = <<-EOT
    Secrets Manager secrets to create. `governance-mcp` holds the token-signing key;
    `notify-hmac` is the shared HMAC secret the runner signs with and the notify-bridge verifies.
  EOT
  type    = list(string)
  default = ["governance-mcp", "notify-hmac"]
}

variable "workload_namespace" {
  description = "Kubernetes namespace the workloads run in (for IRSA trust conditions)."
  type        = string
  default     = "agent-fleet"
}

variable "workload_irsa" {
  description = <<-EOT
    Workloads that need AWS access, keyed by ServiceAccount name. `secrets` lists the short
    service names whose secrets the role may read. Omit a service to grant it no AWS creds.
  EOT
  type = map(object({
    secrets = list(string)
  }))
  default = {
    governance-mcp      = { secrets = ["governance-mcp"] }
    ticket-to-pr-runner = { secrets = ["notify-hmac"] }
    notify-bridge       = { secrets = ["notify-hmac"] }
  }
}

variable "github_repo" {
  description = <<-EOT
    GitHub repo (owner/name) allowed to assume the CI deploy role via OIDC. Leave empty to skip
    creating the OIDC provider, CI role, and its cluster access entry.
  EOT
  type    = string
  default = ""
}

variable "create_github_oidc_provider" {
  description = "Create the account's GitHub OIDC provider. Set false if one already exists."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags merged into the default tag set."
  type        = map(string)
  default     = {}
}
