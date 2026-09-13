variable "name_prefix" { type = string }
variable "region" { type = string }
variable "alb_arn_suffix" { type = string }
variable "rds_instance_id" { type = string }
variable "redis_cluster_id" { type = string }

variable "rds_storage_alarm_threshold_bytes" {
  type    = number
  default = 5368709120 # 5 GiB
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
