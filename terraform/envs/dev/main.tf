provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = var.cluster_name

  # Pick the first two available AZs unless the caller pins them explicitly.
  azs = length(var.azs) > 0 ? var.azs : slice(data.aws_availability_zones.available.names, 0, 2)

  tags = merge({
    Project     = "agent-fleet-on-eks"
    Environment = "dev"
    ManagedBy   = "terraform"
  }, var.tags)

  # ECR repo per service; Secrets Manager secret per entry in var.secrets.
  repo_names   = [for s in var.services : "${local.name}/${s}"]
  secret_names = [for s in var.secrets : "${local.name}/${s}"]
}

module "vpc" {
  source = "../../modules/vpc"

  name               = "${local.name}-vpc"
  cidr               = var.vpc_cidr
  azs                = local.azs
  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
  single_nat_gateway = var.single_nat_gateway
  cluster_name       = local.name
  tags               = local.tags
}

module "eks" {
  source = "../../modules/eks"

  cluster_name    = local.name
  cluster_version = var.cluster_version

  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  node_instance_types = var.node_instance_types
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  node_desired_size   = var.node_desired_size

  endpoint_public_access       = var.endpoint_public_access
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs

  tags = local.tags
}

module "ecr" {
  source = "../../modules/ecr"

  repository_names = local.repo_names
  tags             = local.tags
}

module "secrets" {
  source = "../../modules/secrets"

  secret_names = local.secret_names
  tags         = local.tags
}

# One least-privilege IRSA role per workload that needs AWS access. Each role can read only
# the secrets listed for it. Services not present here (e.g. scheduler) get no AWS creds.
module "irsa" {
  source   = "../../modules/irsa"
  for_each = var.workload_irsa

  role_name         = "${local.name}-${each.key}-irsa"
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider     = module.eks.oidc_provider
  namespace         = var.workload_namespace
  service_account   = each.key
  secret_arns       = [for s in each.value.secrets : module.secrets.secret_arns["${local.name}/${s}"]]
  tags              = local.tags
}

# --- CI/CD: GitHub Actions OIDC deploy role (only when github_repo is set) ---

module "github_oidc" {
  source = "../../modules/github-oidc"
  count  = var.github_repo != "" ? 1 : 0

  github_repo          = var.github_repo
  role_name            = "${local.name}-ci-deploy"
  create_oidc_provider = var.create_github_oidc_provider
  ecr_repository_arns  = values(module.ecr.repository_arns)
  cluster_arn          = module.eks.cluster_arn
  tags                 = local.tags
}

# Grant the CI role cluster access for `helm upgrade`. Kept here (not inside the eks or
# github-oidc module) so the two modules stay independent and Terraform sees no dependency cycle.
resource "aws_eks_access_entry" "ci" {
  count         = var.github_repo != "" ? 1 : 0
  cluster_name  = module.eks.cluster_name
  principal_arn = module.github_oidc[0].role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "ci" {
  count         = var.github_repo != "" ? 1 : 0
  cluster_name  = module.eks.cluster_name
  principal_arn = module.github_oidc[0].role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.ci]
}
