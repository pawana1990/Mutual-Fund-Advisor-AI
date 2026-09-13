variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "domain_name" {
  type        = string
  default     = "dev.aiwealthadvisor.app"
  description = "Base domain for this environment; api./app. subdomains are derived from it."
}

variable "api_image" {
  type        = string
  description = "Full ECR image URI:tag for the FastAPI backend, e.g. <account>.dkr.ecr.<region>.amazonaws.com/ai-wealth-advisor-api:<sha>"
}

variable "web_image" {
  type        = string
  description = "Full ECR image URI:tag for the Next.js frontend."
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN covering *.dev.aiwealthadvisor.app (issued and validated out-of-band)."
}
