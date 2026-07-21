terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.80, < 6.0"
    }
  }

  # Remote state (recommended for teams). Left commented so the quickstart works with local
  # state out of the box. To enable: run terraform/bootstrap/ once, then:
  #   terraform init -backend-config=backend.hcl
  # backend "s3" {
  #   bucket         = "REPLACE-agent-fleet-tfstate"
  #   key            = "envs/dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "agent-fleet-tf-locks"
  #   encrypt        = true
  # }
}
