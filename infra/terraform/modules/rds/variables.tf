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
  type        = list(string)
  description = "Security groups (typically the ECS task SGs) allowed to connect on 5432."
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "replica_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "max_allocated_storage_gb" {
  type    = number
  default = 200
}

variable "database_name" {
  type    = string
  default = "wealth_advisor"
}

variable "master_username" {
  type    = string
  default = "wealth_advisor_admin"
}

variable "multi_az" {
  type    = bool
  default = false
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "create_read_replica" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
