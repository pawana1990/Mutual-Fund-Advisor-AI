# Testing Strategy

## Pyramid

```
        ┌───────────────────────┐
        │   E2E (Playwright)      │   ~20 critical user journeys
        ├───────────────────────┤
        │  Contract / API tests   │   every endpoint, schema-validated
        ├───────────────────────┤
        │  Agent graph tests      │   each LangGraph node, stubbed LLM
        ├───────────────────────┤
        │  Service/unit tests     │   financial_metrics, tax, parsers — the bulk
        └───────────────────────┘
```

## Backend (`apps/api`, pytest)

- **Financial correctness is non-negotiable**: `services/financial_metrics.py`
  (XIRR, CAGR, Beta, Alpha, Sharpe, Sortino, volatility, max drawdown) is
  tested against hand-computed fixtures and cross-checked against known
  reference values (e.g. XIRR of a simple two-cashflow series matches the
  closed-form IRR; Sharpe ratio of a zero-volatility series is `inf`/handled
  explicitly, not a crash). Property-based tests (`hypothesis`) assert
  invariants (e.g. XIRR is scale-invariant under uniform cashflow scaling).
- **Parsers** (`services/parsers/*`) are tested against redacted sample
  statements for each source (CAMS/KFin/Groww/Zerodha/CSV/Excel) checked into
  `apps/api/app/tests/fixtures/statements/` — asserts exact transaction
  counts/amounts, and that malformed input raises `ParserError`, never
  silently drops rows.
- **Agents** (`agents/*`) are tested as pure functions with a
  `FakeChatModel` that returns scripted responses — verifies the graph
  topology (right agents invoked for a given chat intent), the guardrail
  validator (a recommendation citing a number absent from
  `supporting_metrics` is rejected), and that every emitted `Recommendation`
  has non-empty `reason`/`risk`/`expected_benefit`.
- **API layer**: `httpx.AsyncClient` + a Postgres testcontainer (real DB, not
  mocks) per test module; RLS/tenant-isolation is asserted explicitly (see
  `SECURITY.md`).
- **Coverage gate**: 85% minimum on `services/` and `agents/`, enforced in CI
  (`pytest --cov --cov-fail-under=85`).

## Frontend (`apps/web`)

- **Unit/component**: Vitest + React Testing Library for
  `HealthScoreGauge`, `AllocationChart`, `RecommendationCard`, etc. —
  snapshot + interaction tests (dark mode, empty states, loading states).
- **E2E**: Playwright against a docker-compose'd full stack in CI — signup →
  import a sample CAMS CSV → see dashboard populate → ask the AI chat a
  question → download a PDF report.
- **Accessibility**: `axe-core` assertions in the Playwright suite (WCAG 2.1
  AA) on every top-level page.
- **Visual regression**: Chromatic (or Playwright screenshot diffing) on the
  dashboard and report PDF layout.

## Load & chaos

- **Load testing** (k6): dashboard read path (materialized snapshot — must
  hold p95 < 200ms at 500 rps), import pipeline (sustained 50 concurrent
  statement uploads), chat endpoint (LLM-bound, tested for graceful
  degradation/backpressure, not raw throughput).
- **Chaos**: Fargate task kill, RDS failover drill, Redis eviction — verify
  the app degrades (cached data served stale, cache-miss retried) rather than
  500s cascading.

## AI-specific evaluation

- **Golden dataset** of ~200 portfolio scenarios with expert-reviewed
  expected recommendation *directions* (not exact text) — a CI job runs the
  full agent pipeline against them and flags drift (e.g. recommendation
  direction flips) for human review before a prompt/model change ships.
- **Hallucination guard test**: fuzz `supporting_metrics` with out-of-range
  values and assert the guardrail validator (`agents/guardrails.py`) still
  catches ungrounded claims.

## CI gates (see `.github/workflows/`)

`backend-ci.yml`: lint (`ruff`) → typecheck (`mypy`) → unit+contract tests →
coverage gate → `bandit`/`pip-audit`.
`frontend-ci.yml`: lint (`eslint`) → typecheck (`tsc`) → unit tests → build →
Playwright E2E against docker-compose.
`terraform-plan.yml`: `terraform fmt -check`, `validate`, `tflint`, `tfsec`,
and a `plan` posted as a PR comment for review before apply.
