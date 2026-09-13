variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "app_security_group_ids" {
  type = list(string)
}

variable "node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "num_cache_clusters" {
  type        = number
  default     = 1
  description = "1 for dev (single node, no HA). 2+ enables automatic failover for prod."
}

variable "snapshot_retention_days" {
  type    = number
  default = 3
}

variable "tags" {
  type    = map(string)
  default = {}
}
