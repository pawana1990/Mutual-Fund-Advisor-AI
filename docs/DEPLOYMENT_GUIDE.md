# AWS Deployment Guide

## Prerequisites

- AWS account with an administrator or scoped deployment role.
- Terraform >= 1.7, AWS CLI v2 configured.
- A registered domain (Route 53 hosted zone) for `aiwealthadvisor.app`.
- Secrets prepared in advance: `OPENAI_API_KEY`, Cognito app config, S3
  bucket names — stored in AWS Secrets Manager (Terraform creates the
  Secrets Manager entries; you fill in the values via console/CLI, never in
  `.tfvars` committed to git).

## Environments

`infra/terraform/environments/{dev,prod}` — same modules, different sizing
and count (`dev`: single-AZ RDS, 1 ECS task per service, no WAF rate
throttling; `prod`: Multi-AZ RDS + read replica, 2+ ECS tasks with
autoscaling, WAF + Shield Standard).

## One-time bootstrap

```bash
cd infra/terraform/environments/dev
terraform init -backend-config=backend.hcl   # S3 backend + DynamoDB lock table
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

This provisions: VPC, RDS Postgres (+pgvector extension via
`aws_rds_cluster_parameter_group` bootstrap script), ElastiCache Redis, S3
buckets, Cognito user pool + app client, ECR repositories, ECS cluster +
services (initially at `desired_count = 0` until the first image is pushed),
ALB + target groups, CloudWatch log groups, IAM roles/policies scoped
per-service.

## Build & push images

```bash
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com

docker build -t ai-wealth-advisor-api:latest ./apps/api
docker tag ai-wealth-advisor-api:latest <account>.dkr.ecr.ap-south-1.amazonaws.com/ai-wealth-advisor-api:latest
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/ai-wealth-advisor-api:latest

docker build -t ai-wealth-advisor-web:latest ./apps/web
docker tag ai-wealth-advisor-web:latest <account>.dkr.ecr.ap-south-1.amazonaws.com/ai-wealth-advisor-web:latest
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/ai-wealth-advisor-web:latest
```

In practice this is done by `.github/workflows/deploy.yml` on merge to
`main` (dev) and on a version tag (prod), via OIDC federation to an
`ai-wealth-advisor-deployer` IAM role — **no long-lived AWS keys in GitHub
Secrets**.

## Deploy (update ECS services)

```bash
terraform apply -var="api_image_tag=$(git rev-parse --short HEAD)" \
                 -var="web_image_tag=$(git rev-parse --short HEAD)" \
                 -var="ecs_desired_count=2"
```

ECS performs a rolling deployment (min healthy 100%, max 200%) behind the
ALB; the deployment is gated on the target group's `/healthz` check passing.
Database migrations run as a one-off ECS `RunTask` (`alembic upgrade head`)
in the deploy pipeline **before** the service update, so a bad migration
fails the pipeline before traffic shifts.

## Rollback

```bash
terraform apply -var="api_image_tag=<previous-sha>" -var="web_image_tag=<previous-sha>"
```

Because ECS task definitions are versioned and RDS migrations are
additive-first (expand/contract pattern — never drop a column in the same
release that stops writing to it), rolling back the image is safe without a
corresponding DB rollback in the common case.

## Post-deploy verification

1. `GET /healthz` and `GET /readyz` on the new tasks.
2. Synthetic canary (CloudWatch Synthetics) runs: login → fetch dashboard →
   ask one chat question.
3. Grafana "golden signals" dashboard checked for error-rate/latency
   regressions for 15 minutes before considering the deploy complete.

## DNS & TLS

Route 53 → CloudFront (web) / ALB (api) via ACM certificates
(`*.aiwealthadvisor.app`), auto-renewed. CloudFront distribution has WAF
attached (managed rule groups + rate limiting) in front of the S3-hosted
static Next.js export or the ECS `web` service (SSR mode) depending on
whether server rendering is required for a given route.
