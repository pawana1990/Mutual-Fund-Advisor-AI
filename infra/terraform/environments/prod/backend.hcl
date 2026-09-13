# Usage: terraform init -backend-config=backend.hcl
bucket         = "ai-wealth-advisor-tfstate-prod"
key            = "prod/terraform.tfstate"
region         = "ap-south-1"
dynamodb_table = "ai-wealth-advisor-tflock-prod"
encrypt        = true
