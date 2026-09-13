variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN covering both the web and api hostnames."
}

variable "api_hostname" {
  type    = string
  default = "api.aiwealthadvisor.app"
}

variable "enable_deletion_protection" {
  type    = bool
  default = false
}

variable "access_logs_bucket" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
