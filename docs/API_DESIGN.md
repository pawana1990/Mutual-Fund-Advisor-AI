# API Design

Base URL: `https://api.aiwealthadvisor.app/api/v1` (local: `http://localhost:8000/api/v1`)

## Conventions

- **REST** for CRUD-shaped resources and imports; **GraphQL** (`/graphql`,
  Strawberry-GraphQL over the same service layer) for the dashboard's
  composite, deeply-nested reads (one round trip for portfolio + holdings +
  health score + recommendations + alerts) to avoid REST waterfalling.
- Auth: `Authorization: Bearer <Cognito JWT>` on every request. The API
  validates signature via Cognito JWKS, then loads `organization_id`, `role`
  from the token's custom claims and sets the Postgres session variable used
  by RLS.
- All list endpoints are cursor-paginated: `?limit=25&cursor=<opaque>`.
- All monetary fields are strings in the wire format (`"124500.00"`) to avoid
  float precision bugs; percentages are numbers with 2 decimal places.
- Errors follow RFC 7807 `application/problem+json`:
  `{"type", "title", "status", "detail", "instance", "errors": [...]}`.
- Idempotency: mutating endpoints accept `Idempotency-Key` header (imports,
  recommendation accept/dismiss) to make client retries safe.
- Rate limiting: token bucket per user (100 req/min) and per IP (500 req/min)
  enforced at the API layer via Redis + reflected as `429` with
  `Retry-After`.

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | proxy to Cognito `SignUp`, creates `users` row on confirm webhook |
| POST | `/auth/login` | Cognito `InitiateAuth` (or handled client-side via Hosted UI/Amplify) |
| POST | `/auth/refresh` | refresh access token |
| GET | `/auth/me` | current user profile + role + organization |

## Portfolio

| Method | Path | Description |
|---|---|---|
| GET | `/portfolios` | list portfolios for current user (or all clients, if `advisor`) |
| POST | `/portfolios` | create a portfolio |
| GET | `/portfolios/{id}` | portfolio detail |
| GET | `/portfolios/{id}/holdings` | current holdings with live value |
| GET | `/portfolios/{id}/transactions` | paginated transaction ledger |
| GET | `/portfolios/{id}/snapshot` | latest materialized snapshot (value, XIRR, allocation) |
| GET | `/portfolios/{id}/snapshot/history?range=1y` | time series for the value/XIRR chart |
| POST | `/portfolios/{id}/recompute` | force a full agent re-run (rate-limited, e.g. after manual holding edit) |
| GET | `/portfolios/{id}/health-score` | latest score + sub-scores + explanation |

## Funds (reference data, shared across tenants)

| Method | Path | Description |
|---|---|---|
| GET | `/funds/search?q=` | typeahead search by name/ISIN/AMC |
| GET | `/funds/{id}` | fund detail: NAV, expense ratio, manager, AUM, benchmark |
| GET | `/funds/{id}/risk-metrics?window=3y` | beta/alpha/sharpe/sortino/std-dev/drawdown |
| GET | `/funds/{id}/rolling-returns` | rolling 1y/3y/5y return series |
| GET | `/funds/compare?ids=a,b` | side-by-side comparison payload used by the AI chat "compare two funds" flow |

## Risk

| Method | Path | Description |
|---|---|---|
| GET | `/portfolios/{id}/risk` | portfolio-level beta/alpha/sharpe/sortino/volatility/max-drawdown with plain-English explanation per metric |
| GET | `/portfolios/{id}/overlap` | duplicate holdings, overlap %, AMC/sector concentration |

## Recommendations

| Method | Path | Description |
|---|---|---|
| GET | `/portfolios/{id}/recommendations?status=open` | list, each with `reason`, `supporting_metrics`, `risk`, `expected_benefit` |
| POST | `/recommendations/{id}/accept` | mark accepted (audit-logged, does NOT auto-trade — Phase 1 has no broker execution) |
| POST | `/recommendations/{id}/dismiss` | mark dismissed with optional user feedback, used to fine-tune future ranking |

## Goals

| Method | Path | Description |
|---|---|---|
| GET/POST | `/portfolios/{id}/goals` | list / create a goal |
| GET | `/goals/{id}/projection` | Monte-Carlo fan chart (P10/P25/P50/P75/P90) + required SIP |
| PATCH | `/goals/{id}` | update target amount/date, triggers projection recompute |

## Tax

| Method | Path | Description |
|---|---|---|
| GET | `/portfolios/{id}/tax?fy=2025-26` | LTCG/STCG, tax payable, exit-load-adjusted |
| GET | `/portfolios/{id}/tax/harvesting-opportunities` | ranked list with estimated tax saved |

## Chat (AI)

| Method | Path | Description |
|---|---|---|
| POST | `/portfolios/{id}/chat` | `{message}` → streamed (SSE) response; internally invokes the LangGraph supervisor which routes to one or more agents and returns a grounded answer + citations to the metrics/rows used |
| GET | `/portfolios/{id}/chat/history` | paginated session history |

## Reports

| Method | Path | Description |
|---|---|---|
| POST | `/portfolios/{id}/reports` | queue a PDF report generation job, returns `report_id` |
| GET | `/reports/{id}` | status + presigned S3 download URL once `ready` |

## Imports

| Method | Path | Description |
|---|---|---|
| POST | `/imports/upload-url` | `{source_type}` → presigned S3 PUT URL + `import_job_id` |
| GET | `/imports/{job_id}` | status, row counts, any rows flagged `needs_review` |
| POST | `/imports/{job_id}/rows/{row_id}/resolve` | manually correct an ambiguous parsed row (e.g. unmatched ISIN) |

## Notifications

| Method | Path | Description |
|---|---|---|
| GET | `/alerts` | list, filterable by type/severity/read state |
| PATCH | `/alerts/{id}/read` | mark read |
| PATCH | `/users/me/notification-prefs` | toggle email/WhatsApp/push per alert type |

## GraphQL (dashboard composite reads)

```graphql
query Dashboard($portfolioId: ID!) {
  portfolio(id: $portfolioId) {
    snapshot { investedValue currentValue xirr assetAllocation sectorAllocation amcAllocation topHoldings }
    healthScore { overall diversification risk returns fees fundQuality taxEfficiency assetAllocationScore goalReadiness explanation }
    recommendations(status: OPEN) { action reason supportingMetrics risk expectedBenefit }
    alerts(unreadOnly: true) { type severity title createdAt }
    goals { type targetAmount targetDate requiredMonthlySip probabilityOfSuccess }
    upcomingSips { fundName amount nextDebitDate }
  }
}
```

## Versioning & deprecation

Path-versioned (`/api/v1`, `/api/v2`); a `Sunset` + `Deprecation` header pair
is added at least 6 months before a version is retired. Breaking changes
never land in `v1` — only additive fields.
