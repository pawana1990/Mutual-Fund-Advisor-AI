output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "ecr_api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  value = module.cognito.app_client_id
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "cloudwatch_dashboard" {
  value = module.observability.dashboard_name
}
