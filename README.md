# AI Wealth Advisor

AI Wealth Advisor is a production-grade, AI-first SaaS platform that analyzes an
investor's portfolio, continuously monitors holdings, quantifies risk, explains
performance in plain English, and produces evidence-backed recommendations for
long-term wealth creation.

Phase 1 focuses on **Mutual Funds** (India-first: CAMS/KFin/Groww/Zerodha Coin/ET
Money/Kuvera imports, LTCG/STCG tax rules). The architecture is deliberately
modular so Stocks, ETFs, Gold, Bonds, NPS, EPF, FDs, REITs, international funds
and crypto can be added as new `AssetClass` providers without touching the core
domain model.

> The product never says "buy" or "sell" without showing the metrics and
> reasoning behind it. Every recommendation carries `reason`, `supporting_metrics`,
> `risk`, and `expected_benefit`.

## Repository layout

```
.
├── apps/
│   ├── api/                # FastAPI backend (Python 3.12) — domain, agents, services
│   └── web/                 # Next.js 14 + TypeScript + Tailwind + ShadCN UI
├── infra/terraform/         # AWS infrastructure as code (VPC, ECS Fargate, RDS, etc.)
├── docs/                    # Architecture, schema, API, agent workflow, security, ops docs
├── docker-compose.yml        # Local dev stack: Postgres+pgvector, Redis, API, Web
└── .github/workflows/        # CI/CD pipelines
```

Start here:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — high-level system + microservice architecture
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — ERD and table definitions
- [`docs/API_DESIGN.md`](docs/API_DESIGN.md) — REST + GraphQL surface, auth model
- [`docs/AI_AGENT_WORKFLOW.md`](docs/AI_AGENT_WORKFLOW.md) — LangGraph multi-agent design
- [`docs/SECURITY.md`](docs/SECURITY.md) — OWASP Top 10, encryption, RBAC, tenancy
- [`docs/TESTING_STRATEGY.md`](docs/TESTING_STRATEGY.md)
- [`docs/MONITORING.md`](docs/MONITORING.md)
- [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)
- [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md)

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, TailwindCSS, ShadCN UI, Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| AI orchestration | LangGraph, LangChain, OpenAI (model configurable, defaults to latest GPT) |
| Database | PostgreSQL 16 |
| Vector store | pgvector (fund factsheets, news, RAG over SEBI circulars) |
| Cache / queue | Redis (cache, rate limiting, Celery broker) |
| Object storage | Amazon S3 (statements, generated PDF reports) |
| Auth | AWS Cognito (JWT, OAuth2/OIDC) + RBAC |
| Deployment | Docker, Amazon ECS Fargate, Application Load Balancer |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Observability | CloudWatch, Grafana + Prometheus |

## Quick start (local development)

```bash
cp .env.example .env            # fill in OPENAI_API_KEY etc.
docker compose up --build       # postgres, redis, api (:8000), web (:3000)

# backend tests (financial-metrics engine, agents, parsers)
cd apps/api && pip install -e ".[dev]" && pytest

# frontend
cd apps/web && npm install && npm run dev
```

API docs are served at `http://localhost:8000/docs` (OpenAPI/Swagger) once the
backend is running.

## Design principles

1. **Evidence over assertion.** Every AI output is grounded in computed metrics
   (XIRR, CAGR, Sharpe, Sortino, Beta, Alpha, drawdown, overlap %, expense
   ratio deltas) that are always returned alongside the natural-language
   explanation, never replaced by it.
2. **Agents, not one giant prompt.** Each specialized concern (portfolio
   analysis, fund research, overlap detection, risk, recommendations, goals,
   tax, news) is an independent LangGraph node with a narrow, typed
   input/output contract, orchestrated by a supervisor graph. See
   `apps/api/app/agents/`.
3. **Multi-tenant from day one.** Every table is scoped by `tenant_id` /
   `user_id`; row-level access is enforced in the query layer, not just the API
   layer.
4. **Explainability is a first-class API contract**, not a UI afterthought —
   `Recommendation.reason`, `.supporting_metrics`, `.risk`, `.expected_benefit`
   are required (non-nullable) fields.
