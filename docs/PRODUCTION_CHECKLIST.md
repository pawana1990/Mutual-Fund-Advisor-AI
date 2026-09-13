# Production Readiness Checklist

## Architecture & code
- [ ] All Phase-1 services (portfolio, funds, risk, recommendations, goals,
      tax, chat, reports, imports, notifications) behind FastAPI routers with
      Pydantic request/response schemas (no untyped `dict` responses).
- [ ] Every `Recommendation` has non-null `reason`, `supporting_metrics`,
      `risk`, `expected_benefit` enforced at the DB (`NOT NULL`) and schema
      level.
- [ ] Financial metrics (`services/financial_metrics.py`) unit-tested against
      hand-verified fixtures; coverage ≥ 85%.
- [ ] Agent guardrail validator (`agents/guardrails.py`) rejects ungrounded
      recommendations; covered by fuzz tests.
- [ ] No secrets in source control (`gitleaks` clean).

## Data
- [ ] Alembic migrations reviewed for RLS policies + enum additions (not
      autogenerate-only).
- [ ] Backups: RDS automated snapshots (7-day PITR minimum, 35-day in prod)
      + tested restore drill.
- [ ] `pgvector` extension enabled and indexed (`ivfflat`/`hnsw`) for
      `kb_chunks`.
- [ ] Data retention & deletion (GDPR erasure) job tested end-to-end.

## Security
- [ ] Cognito MFA enforced for `advisor`/`admin` roles.
- [ ] RLS policies present on every tenant-scoped table; tenant-isolation
      test suite passing.
- [ ] WAF managed rules + rate limiting attached to CloudFront/ALB.
- [ ] `bandit`, `pip-audit`, `npm audit`, `tfsec` all clean or exceptions
      documented and risk-accepted.
- [ ] Pen test / security review completed before public launch (see
      `SECURITY.md` — SEBI/regulatory classification reviewed with counsel).
- [ ] Least-privilege IAM roles per ECS task verified (no `*` resource
      policies).

## Reliability
- [ ] Multi-AZ RDS + read replica in prod; ElastiCache in cluster mode.
- [ ] ECS services autoscale on CPU + custom queue-depth metric.
- [ ] Health checks (`/healthz`, `/readyz`) wired to ALB target groups.
- [ ] Chaos drills executed (task kill, RDS failover, Redis eviction) with
      documented outcomes.
- [ ] Graceful degradation verified: OpenAI outage → dashboard still serves
      last-known metrics with a visible "AI insights delayed" banner.

## Performance
- [ ] Dashboard read path p95 < 300ms under 500 rps load test.
- [ ] Materialized `portfolio_snapshots` in place — no live recomputation on
      the hot read path.
- [ ] DB indexes reviewed against `pg_stat_statements` slow-query log.
- [ ] Frontend Lighthouse score ≥ 90 (performance, accessibility, best
      practices) on the dashboard route.

## Observability
- [ ] Structured logs flowing to CloudWatch with correlation IDs.
- [ ] Grafana dashboards (golden signals, AI ops, business, data pipeline)
      live and reviewed weekly.
- [ ] Alarms wired to on-call (PagerDuty/Ops Genie) for the SLOs in
      `MONITORING.md`.
- [ ] Cost-per-active-portfolio dashboard live; LLM spend alarm configured.

## Compliance & legal
- [ ] Privacy policy + terms of service published; consent capture wired to
      `users.consent_json`.
- [ ] Data processing agreement templates ready for advisor/enterprise
      tenants.
- [ ] Regulatory classification (SEBI Investment Adviser vs. execution-only
      tool) confirmed with counsel.
- [ ] Audit log retention policy documented and automated (S3 Glacier
      export).

## Launch operations
- [ ] Runbooks published for top 5 failure modes.
- [ ] On-call rotation staffed.
- [ ] Rollback procedure rehearsed (see `DEPLOYMENT_GUIDE.md`).
- [ ] Feature flags in place for any launch-risky feature (recommendation
      auto-generation can be killed independently of the rest of the app).
- [ ] Customer support playbook for "the AI told me to exit a fund and it
      went up" style tickets — reinforcing the evidence-shown, no-execution
      product framing.
