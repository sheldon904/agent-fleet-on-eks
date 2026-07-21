output "state_bucket_name" {
  description = "S3 bucket holding Terraform state. Put this in envs/dev/backend.hcl."
  value       = aws_s3_bucket.state.id
}

output "lock_table_name" {
  description = "DynamoDB lock table. Put this in envs/dev/backend.hcl."
  value       = aws_dynamodb_table.locks.name
}

output "backend_hcl" {
  description = "Copy this into terraform/envs/dev/backend.hcl."
  value       = <<-EOT
    bucket         = "${aws_s3_bucket.state.id}"
    key            = "envs/dev/terraform.tfstate"
    region         = "${var.region}"
    dynamodb_table = "${aws_dynamodb_table.locks.name}"
    encrypt        = true
  EOT
}
