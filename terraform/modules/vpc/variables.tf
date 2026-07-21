variable "name" {
  description = "Name for the VPC and derived resources."
  type        = string
}

variable "cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across."
  type        = list(string)
}

variable "private_subnets" {
  description = "Private subnet CIDRs (one per AZ). Nodes and pods live here."
  type        = list(string)
}

variable "public_subnets" {
  description = "Public subnet CIDRs (one per AZ). NAT gateway and public load balancers live here."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway for all AZs (cheaper, dev). Set false for one-per-AZ HA."
  type        = bool
  default     = true
}

variable "cluster_name" {
  description = "EKS cluster name, used to tag subnets for cluster/LB discovery. Empty to skip."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
