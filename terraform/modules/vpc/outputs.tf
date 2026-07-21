output "vpc_id" {
  description = "The VPC ID."
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (nodes/pods)."
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs (NAT, public LBs)."
  value       = module.vpc.public_subnets
}

output "nat_public_ips" {
  description = "Public IPs of the NAT gateway(s) — useful for egress allow-listing."
  value       = module.vpc.nat_public_ips
}
