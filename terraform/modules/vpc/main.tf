# modules/vpc — curated wrapper around the upstream VPC module.
# We expose only the inputs the fleet needs and set opinionated, cost-aware defaults.
# Upstream: https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = var.name
  cidr = var.cidr

  azs             = var.azs
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  # NAT: single gateway in dev (saves ~$66/mo vs one-per-AZ). Flip single_nat_gateway
  # to false for a production HA layout (one NAT per AZ).
  enable_nat_gateway     = true
  single_nat_gateway     = var.single_nat_gateway
  one_nat_gateway_per_az = !var.single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  # Subnet tags so the AWS Load Balancer Controller and EKS can auto-discover subnets.
  public_subnet_tags = merge(
    { "kubernetes.io/role/elb" = "1" },
    var.cluster_name != "" ? { "kubernetes.io/cluster/${var.cluster_name}" = "shared" } : {}
  )
  private_subnet_tags = merge(
    { "kubernetes.io/role/internal-elb" = "1" },
    var.cluster_name != "" ? { "kubernetes.io/cluster/${var.cluster_name}" = "shared" } : {}
  )

  tags = var.tags
}
