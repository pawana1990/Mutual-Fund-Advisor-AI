variable "name_prefix" {
  type        = string
  description = "Prefix applied to every resource name (e.g. \"ai-wealth-advisor-dev\")."
}

variable "region" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  type        = number
  default     = 2
  description = "Number of Availability Zones to spread public/private subnets across."
}

variable "single_nat_gateway" {
  type        = bool
  default     = true
  description = "Use one shared NAT Gateway (cost-optimized for dev) instead of one per AZ (HA, for prod)."
}

variable "tags" {
  type    = map(string)
  default = {}
}
