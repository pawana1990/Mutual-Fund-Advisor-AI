variable "name_prefix" {
  type = string
}

variable "callback_urls" {
  type    = list(string)
  default = ["http://localhost:3000/api/auth/callback"]
}

variable "logout_urls" {
  type    = list(string)
  default = ["http://localhost:3000"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
