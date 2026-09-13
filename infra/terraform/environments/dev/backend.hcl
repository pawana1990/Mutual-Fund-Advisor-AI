# Usage: terraform init -backend-config=backend.hcl
# Create the bucket + DynamoDB lock table once, by hand or in a separate
# bootstrap Terraform root, before running this.
bucket         = "ai-wealth-advisor-tfstate-dev"
key            = "dev/terraform.tfstate"
region         = "ap-south-1"
dynamodb_table = "ai-wealth-advisor-tflock-dev"
encrypt        = true
