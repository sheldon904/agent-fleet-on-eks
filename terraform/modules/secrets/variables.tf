variable "secret_names" {
  description = "Secrets Manager secret names to create (e.g. agent-fleet/notify-bridge)."
  type        = list(string)
}

variable "recovery_window_in_days" {
  description = "0 force-deletes on destroy (dev). Use 7-30 in production."
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags applied to all secrets."
  type        = map(string)
  default     = {}
}
