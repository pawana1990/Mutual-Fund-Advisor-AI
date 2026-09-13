# High-Level Architecture

## 1. System context

```
                                   ┌─────────────────────────┐
                                   │        End Users         │
                                   │ (retail, HNI, advisors,  │
                                   │  wealth management firms)│
                                   └────────────┬─────────────┘
                                                │ HTTPS
                                   ┌────────────▼─────────────┐
                                   │   CloudFront + WAF (CDN)  │
                                   └────────────┬─────────────┘
                     ┌─────────────────────────┼─────────────────────────┐
                     │                                                     │
          ┌──────────▼───────────┐                              ┌──────────▼───────────┐
          │  Next.js Web App      │                              │  ALB (public subnets) │
          │  (ECS Fargate/S3+CF)  │                              └──────────┬───────────┘
          └──────────┬────────────┘                                        │
                     │ REST/GraphQL (JWT)                          ┌────────▼─────────┐
                     └─────────────────────────────────────────────►  FastAPI Gateway   │
                                                                    │  (ECS Fargate,     │
                                                                    │   private subnet)  │
                                                                    └──┬───────┬───────┬─┘
                        ┌────────────────────────────────────────────┘       │       └────────────────────────┐
                        │                                                     │                                 │
              ┌─────────▼─────────┐                                ┌─────────▼─────────┐            ┌──────────▼──────────┐
              │ Portfolio Service  │                                │  AI Agent Service   │            │ Import/Parsing Svc   │
              │ (metrics, health   │                                │  (LangGraph          │            │ (CAMS/KFin/Groww/   │
              │  score, holdings)  │                                │   supervisor +       │            │  Zerodha/CSV/XLSX/  │
              └─────────┬─────────┘                                │   8 specialist       │            │  PDF → normalized    │
                        │                                          │   agents)            │            │  transactions)        │
              ┌─────────▼─────────┐                                └─────────┬─────────┘            └──────────┬──────────┘
              │ Fund Research Svc  │                                          │                                  │
              │ (NAV, expense,     │                                ┌─────────▼─────────┐            ┌──────────▼──────────┐
              │  ratings, RAG)     │                                │  OpenAI (LLM +       │            │   Amazon S3          │
              └─────────┬─────────┘                                │  embeddings)         │            │  (raw statements,     │
                        │                                          └─────────────────────┘            │   generated reports)  │
       ┌────────────────┼─────────────────────┬──────────────────────────┬──────────────────┐         └───────────────────────┘
┌──────▼──────┐  ┌───────▼───────┐  ┌──────────▼─────────┐   ┌───────────▼──────────┐
│ PostgreSQL   │  │ pgvector       │  │ Redis (cache, rate  │   │ Celery workers        │
│ (RDS, multi- │  │ (fund docs,    │  │  limit, Celery      │   │ (news monitoring,     │
│  AZ, primary │  │  news, SEBI    │  │  broker/result      │   │  notifications,       │
│  + read      │  │  circulars     │  │  backend)           │   │  scheduled re-scoring,│
│  replica)    │  │  embeddings)   │  └──────────────────────┘   │  PDF report generation)│
└─────────────┘  └────────────────┘                              └───────────────────────┘
```

## 2. Architectural style

- **Microservices within a modular monolith deployment unit.** Each domain
  (`portfolio`, `funds`, `risk`, `recommendations`, `goals`, `tax`, `chat`,
  `reports`, `notifications`, `imports`) is implemented as an isolated FastAPI
  router + service module with its own SQLAlchemy repository layer. They are
  deployed as **one ECS service** initially (cost-optimized for early scale)
  but are already package-isolated so any module can be extracted into its own
  ECS service/task definition the moment its load profile diverges (e.g. the
  Import/Parsing service is CPU/IO heavy and is the first natural extraction
  candidate — it already runs as an independent Fargate service in the
  reference Terraform).
- **Event-driven side effects.** State changes that need to fan out
  (a new statement imported → re-run Portfolio Analysis → re-run Risk →
  re-run Recommendation → recompute Health Score → notify) are published to a
  Redis Streams / SQS-backed event bus (`portfolio.updated`,
  `nav.refreshed`, `fund.manager_changed`, `tax_year.rolled`) rather than
  called synchronously, so agents can be scaled and retried independently.
- **AI agents are stateless graph nodes.** LangGraph's `StateGraph` holds a
  typed `AdvisorState` (see `AI_AGENT_WORKFLOW.md`); each agent node is a pure
  function `(state) -> state_patch` that can be unit tested without a live LLM
  by injecting a stub `ChatModel`.
- **CQRS-lite for the dashboard.** Expensive aggregates (health score,
  allocation breakdowns, XIRR) are computed by the Portfolio Service on
  write/import and cached in `portfolio_snapshots` (materialized, versioned)
  rather than recomputed per dashboard request; a `snapshot.recompute` job
  invalidates and rebuilds on demand.

## 3. Multi-tenancy model

- SaaS for individual investors AND wealth management firms managing many
  clients ⇒ two-level tenancy: `Organization` (nullable for a self-serve
  retail user — treated as a tenant of one) → `User` → `Portfolio`.
- Every table below `Organization` carries `organization_id` (indexed,
  NOT NULL) and Postgres Row-Level Security policies key off
  `current_setting('app.current_org_id')`, set per-request by the FastAPI
  DB session dependency from the verified JWT — defense in depth beyond the
  ORM-level filtering already applied in every repository query.
- Role-Based Access Control: `owner`, `advisor`, `client_viewer`, `analyst`,
  `admin` — see `SECURITY.md`.

## 4. Deployment topology (AWS)

- **VPC**: 2 AZs, public subnets (ALB, NAT), private subnets (ECS tasks, RDS,
  ElastiCache).
- **ECS Fargate services**: `web`, `api`, `agent-worker` (Celery), `import-worker`.
  Each behind its own target group; `api` and `web` behind the shared ALB with
  path/host-based routing (`app.` → web, `api.` → api).
- **RDS PostgreSQL 16** (Multi-AZ in prod) with `pgvector` extension enabled;
  one read replica for reporting/analytics queries.
- **ElastiCache Redis** (cluster mode disabled for cost in dev, enabled in
  prod) for cache, rate limiting (token bucket per user/IP), and Celery
  broker/result backend.
- **S3**: `statements/` (raw imports, versioned, SSE-KMS), `reports/`
  (generated PDFs, presigned-URL access only).
- **Cognito**: user pools with hosted UI for auth, custom attributes for
  `organization_id` and `role`; App Client uses Authorization Code + PKCE from
  the Next.js app; FastAPI validates the RS256 JWT against Cognito's JWKS.
- **CloudFront + WAF** in front of the static Next.js assets and the ALB
  (rate-based rule, AWS Managed Core Rule Set, geo-restriction optional).
- **Secrets Manager** for `DATABASE_URL`, `OPENAI_API_KEY`, etc. — injected
  into ECS task definitions as secrets, never as plain environment variables
  in the image or task JSON.
- **CloudWatch** log groups per service + custom metrics (agent latency, LLM
  token spend, XIRR computation errors) exported to **Grafana** via the
  CloudWatch data source (or an AMP/AMG managed Grafana workspace).

## 5. Serverless where applicable

- PDF report generation and statement OCR are bursty → run as **Lambda**
  (via the same `app.services.reports` / `app.services.parsers.pdf_parser`
  code, packaged as a Lambda-compatible handler) triggered by S3
  `ObjectCreated` events, instead of occupying always-on Fargate capacity.
- Scheduled jobs (nightly NAV refresh, weekly news scan, monthly tax-harvest
  scan) run as **EventBridge Scheduler → Lambda / ECS RunTask**, not a
  perpetually-running cron container.

## 6. Data flow: "user connects a CAMS statement"

1. Web app requests a presigned S3 PUT URL from `POST /api/v1/imports/upload-url`.
2. Browser uploads the PDF/CSV directly to S3 (never through the API tier).
3. S3 event → SQS → `import-worker` picks it up, `services/parsers/detector.py`
   sniffs the format, the matching parser normalizes rows into
   `Transaction` + `Holding` records inside a DB transaction.
4. On commit, an `portfolio.updated` event is published.
5. The **Portfolio Analysis Agent** consumes it, recomputes XIRR/CAGR/
   allocation, writes a new `PortfolioSnapshot`.
6. This fans out to **Overlap Detection**, **Risk Analysis**, **Recommendation**,
   **Tax** agents (parallel LangGraph branches), each writing their typed
   output rows.
7. The **Health Score** service aggregates all of the above into the 0–100
   score + category breakdown.
8. **Notification service** diffs the new recommendations/alerts against the
   last snapshot and sends only the deltas (email/WhatsApp/push).
9. The dashboard reads exclusively from the materialized snapshot tables — no
   heavy computation on the request path.
