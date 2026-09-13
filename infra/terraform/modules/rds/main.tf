terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.name_prefix}-rds-"
  description = "Allow Postgres access from the app tier only."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.app_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-rds-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_kms_key" "rds" {
  description             = "${var.name_prefix} RDS encryption-at-rest key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "random_password" "master" {
  length      = 32
  special     = false # avoid characters the Postgres connection string would need escaping
  min_upper   = 1
  min_lower   = 1
  min_numeric = 1
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.name_prefix}/rds/master-credentials"
  description = "Master credentials for the ${var.name_prefix} RDS instance"
  kms_key_id  = aws_kms_key.rds.key_id
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.master.result
    engine   = "postgres"
    host     = aws_db_instance.this.address
    port     = 5432
    dbname   = var.database_name
    url      = "postgresql+asyncpg://${var.master_username}:${random_password.master.result}@${aws_db_instance.this.address}:5432/${var.database_name}"
  })
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name_prefix}-pg16-"
  family      = "postgres16"
  description = "Enables pgvector + sensible defaults for ${var.name_prefix}"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  multi_az                    = var.multi_az
  backup_retention_period     = var.backup_retention_days
  backup_window                = "18:00-19:00" # UTC ~= late night IST
  maintenance_window            = "sun:19:00-sun:20:00"
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = !var.deletion_protection
  final_snapshot_identifier    = var.deletion_protection ? "${var.name_prefix}-final-snapshot" : null
  performance_insights_enabled = true
  copy_tags_to_snapshot        = true
  auto_minor_version_upgrade   = true

  tags = var.tags
}

resource "aws_db_instance" "read_replica" {
  count               = var.create_read_replica ? 1 : 0
  identifier          = "${var.name_prefix}-postgres-replica"
  replicate_source_db = aws_db_instance.this.identifier
  instance_class      = var.replica_instance_class
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.rds.arn
  publicly_accessible = false
  auto_minor_version_upgrade = true
  tags                = var.tags
}
