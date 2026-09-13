locals {
  name_prefix  = "ai-wealth-advisor-prod"
  api_hostname = "api.${var.domain_name}"
  web_hostname = "app.${var.domain_name}"
  tags = {
    Project     = "ai-wealth-advisor"
    Environment = "prod"
  }
}

resource "aws_secretsmanager_secret" "app_secret_key" {
  name = "${local.name_prefix}/app/secret-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${local.name_prefix}/app/openai-api-key"
  tags = local.tags
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.tags
}

resource "aws_ecr_repository" "web" {
  name                 = "${local.name_prefix}-web"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.tags
}

module "vpc" {
  source             = "../../modules/vpc"
  name_prefix        = local.name_prefix
  region             = var.region
  az_count           = 2
  single_nat_gateway = false # one NAT per AZ — no single point of failure in prod
  tags               = local.tags
}

module "s3" {
  source                 = "../../modules/s3"
  name_prefix            = local.name_prefix
  allowed_upload_origins = ["https://${local.web_hostname}"]
  tags                   = local.tags
}

module "cognito" {
  source        = "../../modules/cognito"
  name_prefix   = local.name_prefix
  callback_urls = ["https://${local.web_hostname}/api/auth/callback"]
  logout_urls   = ["https://${local.web_hostname}"]
  tags          = local.tags
}

module "alb" {
  source                     = "../../modules/alb"
  name_prefix                = local.name_prefix
  vpc_id                     = module.vpc.vpc_id
  public_subnet_ids          = module.vpc.public_subnet_ids
  certificate_arn            = var.certificate_arn
  api_hostname               = local.api_hostname
  enable_deletion_protection = true
  # ALB access logs need a dedicated bucket with an ELB-service bucket policy
  # (SSE-S3, not KMS) — provision that separately and set this if/when
  # access-log analysis is needed; CloudWatch + X-Ray already cover the
  # golden-signal and tracing needs described in docs/MONITORING.md.
  access_logs_bucket = ""
  tags                = local.tags
}

resource "aws_security_group" "app_tier_placeholder" {
  name_prefix = "${local.name_prefix}-app-"
  description = "Referenced by RDS/Redis ingress rules; ECS tasks are also members of this group."
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-app-tier-sg" })
}

module "rds" {
  source                 = "../../modules/rds"
  name_prefix            = local.name_prefix
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  app_security_group_ids = [aws_security_group.app_tier_placeholder.id]
  instance_class          = "db.r6g.large"
  replica_instance_class  = "db.r6g.large"
  allocated_storage_gb    = 200
  max_allocated_storage_gb = 1000
  multi_az                = true
  backup_retention_days   = 35
  deletion_protection     = true
  create_read_replica     = true
  tags                    = local.tags
}

module "elasticache" {
  source                 = "../../modules/elasticache"
  name_prefix            = local.name_prefix
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  app_security_group_ids = [aws_security_group.app_tier_placeholder.id]
  node_type              = "cache.r6g.large"
  num_cache_clusters     = 2 # primary + replica, automatic failover
  snapshot_retention_days = 7
  tags                   = local.tags
}

module "ecs" {
  source = "../../modules/ecs"

  name_prefix           = local.name_prefix
  environment           = "prod"
  region                = var.region
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  alb_security_group_id = module.alb.alb_security_group_id
  api_target_group_arn  = module.alb.api_target_group_arn
  web_target_group_arn  = module.alb.web_target_group_arn
  api_hostname          = local.api_hostname

  api_image = var.api_image
  web_image = var.web_image

  statements_bucket_name = module.s3.statements_bucket_name
  statements_bucket_arn  = module.s3.statements_bucket_arn
  reports_bucket_name    = module.s3.reports_bucket_name
  reports_bucket_arn     = module.s3.reports_bucket_arn

  redis_endpoint = module.elasticache.primary_endpoint

  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_app_client_id = module.cognito.app_client_id

  db_credentials_secret_arn = module.rds.credentials_secret_arn
  app_secret_key_arn        = aws_secretsmanager_secret.app_secret_key.arn
  openai_api_key_secret_arn = aws_secretsmanager_secret.openai_api_key.arn
  secret_arns = [
    module.rds.credentials_secret_arn,
    aws_secretsmanager_secret.app_secret_key.arn,
    aws_secretsmanager_secret.openai_api_key.arn,
  ]

  api_cpu              = "1024"
  api_memory           = "2048"
  api_desired_count    = 2
  api_max_count        = 8
  web_cpu              = "512"
  web_memory           = "1024"
  web_desired_count    = 2
  worker_cpu           = "1024"
  worker_memory        = "2048"
  worker_desired_count = 2
  worker_max_count     = 6

  tags = local.tags
}

module "observability" {
  source           = "../../modules/observability"
  name_prefix      = local.name_prefix
  region           = var.region
  alb_arn_suffix   = module.alb.alb_arn_suffix
  rds_instance_id  = module.rds.instance_id
  redis_cluster_id = module.elasticache.primary_cache_cluster_id
  alert_email      = var.alert_email
  tags             = local.tags
}
