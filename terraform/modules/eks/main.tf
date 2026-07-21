# modules/eks — curated wrapper around the upstream EKS module.
# Pinned to v20.x (auth via access entries, IRSA/OIDC provider managed for us).
# Upstream: https://registry.terraform.io/modules/terraform-aws-modules/eks/aws
#
# Upgrade path to v21: rename cluster_name->name, cluster_version->kubernetes_version,
# cluster_addons->addons, and bump the AWS provider to ~> 6.0 in envs/dev/versions.tf.

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  # API server endpoint. Public access is convenient for a demo; restrict the CIDRs
  # (or disable public access and use a bastion/VPN) for production.
  cluster_endpoint_public_access       = var.endpoint_public_access
  cluster_endpoint_public_access_cidrs = var.endpoint_public_access_cidrs
  cluster_endpoint_private_access      = true

  # Modern auth: cluster access entries. Grant the principal running `terraform apply`
  # cluster-admin so `kubectl` works immediately after apply.
  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = true

  # IRSA: create the IAM OIDC provider so workloads can assume scoped IAM roles.
  enable_irsa = true

  vpc_id                   = var.vpc_id
  subnet_ids               = var.private_subnet_ids
  control_plane_subnet_ids = var.private_subnet_ids

  # vpc-cni before_compute so networking is ready before nodes join.
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = { before_compute = true }
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.node_instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = var.node_min_size
      max_size     = var.node_max_size
      desired_size = var.node_desired_size
    }
  }

  tags = var.tags
}
