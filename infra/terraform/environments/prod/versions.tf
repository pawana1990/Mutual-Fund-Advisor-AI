terraform {
  required_version = ">= 1.7"

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

  backend "s3" {
    # Filled in via `terraform init -backend-config=backend.hcl` — kept out
    # of version control since the bucket/table names differ per AWS account.
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "ai-wealth-advisor"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}
