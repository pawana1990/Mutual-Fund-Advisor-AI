# Monitoring & Observability

## Stack

- **CloudWatch**: infra-level metrics (ECS CPU/memory, ALB latency/5xx, RDS
  connections/IOPS, ElastiCache evictions), log groups per service with
  structured JSON logging (`request_id`, `organization_id` [hashed],
  `user_id` [hashed], `latency_ms`).
- **Grafana** (self-hosted on ECS or Amazon Managed Grafana) with CloudWatch
  + Postgres (via `pg_stat_statements`) + a custom Prometheus exporter for
  application metrics, giving four dashboards:
  1. **Golden signals** — request rate, error rate, p50/p95/p99 latency per
     route.
  2. **AI Ops** — agent invocation count/latency/cost per agent type,
     validator rejection rate (recommendations rejected for lacking
     grounding), LLM token spend per day/tenant.
  3. **Business** — DAU/MAU, portfolios synced, imports processed,
     recommendations accepted vs. dismissed, health-score distribution.
  4. **Data pipeline** — NAV refresh job success/latency, news-scan job
     freshness, import-job failure rate by source type.
- **Sentry** (or CloudWatch + X-Ray) for exception tracking with source maps
  (frontend) and stack traces (backend), grouped by release.
- **AWS X-Ray** distributed tracing across ALB → API → DB/Redis/OpenAI calls
  to diagnose slow chat responses (agent-by-agent latency breakdown).

## SLOs

| Service | SLI | SLO |
|---|---|---|
| Dashboard read (`/snapshot`, `/health-score`) | p95 latency | < 300ms |
| Import pipeline | time from upload to "parsed" | < 2 min (p95) for statements < 10MB |
| AI chat first-token | p95 latency | < 3s |
| API availability | monthly uptime | 99.9% |
| NAV freshness | staleness of `funds.current_nav` | < 24h during market days |

## Alerting (PagerDuty/Ops Genie via CloudWatch Alarms → SNS)

- 5xx rate > 2% over 5 min (page).
- p95 latency > 2x SLO for 10 min (page).
- RDS free storage < 15% or replica lag > 30s (page).
- Celery queue depth growing unbounded for > 15 min (ticket).
- LLM guardrail rejection rate > 10% of recommendations in an hour (ticket —
  signals a prompt/model regression).
- Daily LLM spend > configured budget threshold (ticket, cost guardrail).
- Failed login spike (possible credential-stuffing) (page, security).

## Cost observability

AWS Cost Explorer tagged by `service` (api/web/worker/db/cache) and
`environment`; a Grafana panel breaks down **cost per active portfolio**
(infra + LLM token spend) as the core unit economics metric reviewed weekly.

## Runbooks

`docs/runbooks/` (to be expanded as incidents occur) starts with: DB
failover, ECS task crash-loop, OpenAI API outage (fallback: serve
last-known agent outputs + banner "AI insights temporarily delayed", never
block the numeric dashboard), and elevated import-parser failure rate for a
given source (usually means an RTA changed their statement format —
triggers a parser-version alert to engineering).
