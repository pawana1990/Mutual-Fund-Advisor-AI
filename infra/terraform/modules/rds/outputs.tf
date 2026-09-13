output "endpoint" {
  value = aws_db_instance.this.address
}

output "instance_id" {
  value = aws_db_instance.this.identifier
}

output "port" {
  value = aws_db_instance.this.port
}

output "security_group_id" {
  value = aws_security_group.rds.id
}

output "credentials_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}

output "read_replica_endpoint" {
  value = var.create_read_replica ? aws_db_instance.read_replica[0].address : null
}
