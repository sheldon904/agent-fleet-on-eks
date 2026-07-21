variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version. Must be a version EKS currently supports at apply time."
  type        = string
}

variable "vpc_id" {
  description = "VPC to launch the cluster into."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for nodes and the control plane ENIs."
  type        = list(string)
}

variable "node_instance_types" {
  description = "Instance types for the managed node group."
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
  description = "Expose the Kubernetes API server publicly (convenient for demos)."
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint. Restrict this in production."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
