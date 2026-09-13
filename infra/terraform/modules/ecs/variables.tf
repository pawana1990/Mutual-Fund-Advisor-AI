variable "name_prefix" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "api_target_group_arn" { type = string }
variable "web_target_group_arn" { type = string }
variable "api_hostname" { type = string }

variable "api_image" { type = string }
variable "web_image" { type = string }

variable "statements_bucket_name" { type = string }
variable "statements_bucket_arn" { type = string }
variable "reports_bucket_name" { type = string }
variable "reports_bucket_arn" { type = string }

variable "redis_endpoint" { type = string }

variable "cognito_user_pool_id" { type = string }
variable "cognito_app_client_id" { type = string }

variable "db_credentials_secret_arn" { type = string }
variable "app_secret_key_arn" { type = string }
variable "openai_api_key_secret_arn" { type = string }

variable "secret_arns" {
  type        = list(string)
  description = "Every Secrets Manager ARN the execution role must be allowed to read (union of all task secrets)."
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "api_cpu" {
  type    = string
  default = "512"
}
variable "api_memory" {
  type    = string
  default = "1024"
}
variable "api_desired_count" {
  type    = number
  default = 1
}
variable "api_max_count" {
  type    = number
  default = 4
}

variable "web_cpu" {
  type    = string
  default = "256"
}
variable "web_memory" {
  type    = string
  default = "512"
}
variable "web_desired_count" {
  type    = number
  default = 1
}

variable "worker_cpu" {
  type    = string
  default = "512"
}
variable "worker_memory" {
  type    = string
  default = "1024"
}
variable "worker_desired_count" {
  type    = number
  default = 1
}
variable "worker_max_count" {
  type    = number
  default = 3
}

variable "tags" {
  type    = map(string)
  default = {}
}
