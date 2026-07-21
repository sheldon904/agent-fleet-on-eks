variable "region" {
  description = "AWS region for the state bucket and lock table."
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_name" {
  description = "Globally-unique S3 bucket name for Terraform state."
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name for state locks."
  type        = string
  default     = "agent-fleet-tf-locks"
}

variable "tags" {
  description = "Tags applied to the bucket and table."
  type        = map(string)
  default = {
    Project   = "agent-fleet-on-eks"
    ManagedBy = "terraform"
    Purpose   = "tf-remote-state"
  }
}
