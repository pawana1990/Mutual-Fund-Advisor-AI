variable "name_prefix" {
  type = string
}

variable "allowed_upload_origins" {
  type        = list(string)
  description = "Origins (the web app's URL) allowed to PUT directly to the statements bucket via presigned URL."
  default     = ["http://localhost:3000"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
