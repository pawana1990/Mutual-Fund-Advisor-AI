output "statements_bucket_name" {
  value = aws_s3_bucket.statements.id
}

output "statements_bucket_arn" {
  value = aws_s3_bucket.statements.arn
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  value = aws_s3_bucket.reports.arn
}

output "kms_key_arn" {
  value = aws_kms_key.this.arn
}
