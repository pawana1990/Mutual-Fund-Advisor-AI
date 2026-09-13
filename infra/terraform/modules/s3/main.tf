terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_kms_key" "this" {
  description             = "${var.name_prefix} S3 encryption-at-rest key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

# --- Statements bucket: raw user-uploaded CAMS/KFin/Groww/etc statements ---
resource "aws_s3_bucket" "statements" {
  bucket = "${var.name_prefix}-statements"
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "statements" {
  bucket = aws_s3_bucket.statements.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "statements" {
  bucket = aws_s3_bucket.statements.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "statements" {
  bucket                  = aws_s3_bucket.statements.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "statements" {
  bucket = aws_s3_bucket.statements.id
  rule {
    id     = "transition-old-statements"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    noncurrent_version_expiration {
      noncurrent_days = 730
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "statements" {
  bucket = aws_s3_bucket.statements.id
  cors_rule {
    allowed_methods = ["PUT", "GET"]
    allowed_origins = var.allowed_upload_origins
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

# --- Reports bucket: generated PDF reports, accessed only via presigned URL ---
resource "aws_s3_bucket" "reports" {
  bucket = "${var.name_prefix}-reports"
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id     = "expire-old-reports"
    status = "Enabled"
    expiration {
      days = 400
    }
  }
}
