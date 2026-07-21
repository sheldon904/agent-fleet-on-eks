variable "repository_names" {
  description = "ECR repository names to create (e.g. agent-fleet/notify-bridge)."
  type        = list(string)
}

variable "image_tag_mutability" {
  description = "IMMUTABLE (recommended, pairs with SHA tags) or MUTABLE."
  type        = string
  default     = "IMMUTABLE"
}

variable "untagged_expire_days" {
  description = "Expire untagged images older than this many days."
  type        = number
  default     = 14
}

variable "keep_last_images" {
  description = "Keep at most this many images per repo."
  type        = number
  default     = 30
}

variable "force_delete" {
  description = "Allow terraform destroy to delete repos that still contain images (dev)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to all repositories."
  type        = map(string)
  default     = {}
}
