# Database Schema

PostgreSQL 16 with the `pgvector` and `uuid-ossp`/`pgcrypto` extensions.
Every table has `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`,
`created_at`, `updated_at` (trigger-maintained) unless noted. Multi-tenant
tables carry `organization_id` with a Postgres RLS policy
(`USING (organization_id = current_setting('app.current_org_id')::uuid)`).

The SQLAlchemy models mirroring this schema live in `apps/api/app/models/`.

## ERD (core Phase-1 entities)

```
organizations ──< users ──< portfolios ──< holdings >── funds
     │                          │               │           │
     │                          │               │           ├──< fund_nav_history
     │                          │               │           └──< fund_risk_metrics
     │                          │               │
     │                          │               ├──< transactions
     │                          │               ├──< sips
     │                          │               ├──< portfolio_snapshots
     │                          │               ├──< health_scores
     │                          │               ├──< overlap_reports
     │                          │               ├──< recommendations
     │                          │               ├──< tax_records
     │                          │               └──< goals ──< goal_projections
     │                          │
     │                          ├──< alerts
     │                          ├──< chat_sessions ──< chat_messages
     │                          └──< import_jobs ──< import_rows
     │
     └──< audit_logs
```

## Table definitions

### `organizations`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text | |
| plan | enum(`retail_free`,`retail_premium`,`advisor`,`enterprise`) | |
| is_active | boolean | |

### `users`
| column | type | notes |
|---|---|---|
| id | uuid pk | maps to Cognito `sub` |
| organization_id | uuid fk → organizations | |
| email | citext unique | |
| full_name | text | |
| role | enum(`owner`,`advisor`,`client_viewer`,`analyst`,`admin`) | |
| risk_profile | enum(`conservative`,`moderate`,`aggressive`) | from onboarding questionnaire |
| notification_prefs | jsonb | `{email, whatsapp, push}` toggles per alert type |
| is_active | boolean | |

### `portfolios`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| organization_id | uuid fk | |
| owner_user_id | uuid fk → users | the investor whose money this is (an advisor manages many) |
| name | text | e.g. "Retirement", "Primary" |
| base_currency | char(3) | default `INR` |

### `funds` (shared reference data, not tenant-scoped)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| isin | text unique | |
| scheme_code | text | AMFI code |
| name | text | |
| amc | text | Asset Management Company |
| category | text | e.g. "Large Cap", "Flexi Cap" |
| sub_category | text | |
| benchmark | text | |
| fund_manager | text | |
| expense_ratio | numeric(5,2) | percent |
| aum_cr | numeric(14,2) | AUM in ₹ crore |
| exit_load_json | jsonb | tiered exit-load schedule |
| inception_date | date | |
| current_nav | numeric(12,4) | denormalized latest, refreshed nightly |
| current_nav_date | date | |

### `fund_nav_history`
| column | type | notes |
|---|---|---|
| fund_id | uuid fk | |
| nav_date | date | |
| nav | numeric(12,4) | |
| unique(fund_id, nav_date) | | partitioned by year for scale |

### `fund_risk_metrics` (recomputed nightly per fund, rolling windows)
| column | type | notes |
|---|---|---|
| fund_id | uuid fk | |
| window | enum(`1y`,`3y`,`5y`) | |
| cagr | numeric | |
| beta | numeric | |
| alpha | numeric | |
| sharpe_ratio | numeric | |
| sortino_ratio | numeric | |
| std_deviation | numeric | annualized, % |
| max_drawdown | numeric | % |
| category_rank | int | |
| category_size | int | |

### `holdings`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| fund_id | uuid fk | |
| units | numeric(18,4) | |
| avg_cost_nav | numeric(12,4) | |
| invested_value | numeric(16,2) | denormalized sum of buy transactions |
| current_value | numeric(16,2) | `units * fund.current_nav`, refreshed nightly/event |
| source | enum(`cams`,`kfin`,`groww`,`zerodha_coin`,`etmoney`,`kuvera`,`manual`,`csv`,`excel`,`pdf`) | |
| unique(portfolio_id, fund_id) | | |

### `transactions`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| holding_id | uuid fk | |
| fund_id | uuid fk | |
| type | enum(`buy`,`sell`,`sip`,`switch_in`,`switch_out`,`dividend`,`stt`) | |
| date | date | |
| units | numeric(18,4) | |
| nav | numeric(12,4) | |
| amount | numeric(16,2) | signed: +ve inflow to fund, -ve redemption |
| folio_number | text | |
| import_job_id | uuid fk nullable | provenance |

### `sips`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| fund_id | uuid fk | |
| amount | numeric(12,2) | |
| frequency | enum(`monthly`,`quarterly`) | |
| day_of_month | int | |
| status | enum(`active`,`paused`,`stopped`) | |
| next_debit_date | date | |

### `portfolio_snapshots` (materialized, append-only, versioned)
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| as_of | timestamptz | |
| invested_value | numeric(16,2) | |
| current_value | numeric(16,2) | |
| xirr | numeric(7,4) | |
| absolute_return_pct | numeric(7,4) | |
| asset_allocation | jsonb | `{equity: 65, debt: 25, gold: 5, cash: 5}` |
| sector_allocation | jsonb | |
| amc_allocation | jsonb | |
| top_holdings | jsonb | denormalized top-10 for fast dashboard render |

### `health_scores`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| snapshot_id | uuid fk → portfolio_snapshots | |
| overall_score | int | 0–100 |
| diversification_score | int | |
| risk_score | int | |
| returns_score | int | |
| fees_score | int | |
| fund_quality_score | int | |
| tax_efficiency_score | int | |
| asset_allocation_score | int | |
| goal_readiness_score | int | |
| explanation | text | LLM-generated, references the sub-scores above |

### `overlap_reports`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| overlap_pct | numeric(5,2) | portfolio-level stock overlap |
| duplicate_pairs | jsonb | `[{fund_a, fund_b, overlap_pct, common_holdings: [...]}]` |
| amc_concentration | jsonb | `{amc: pct}` |
| sector_overlap | jsonb | |

### `recommendations`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| holding_id | uuid fk nullable | null for allocation-level recs |
| action | enum(`keep`,`increase`,`reduce`,`exit`,`switch`) | |
| switch_target_fund_id | uuid fk nullable | |
| reason | text | required, non-null |
| supporting_metrics | jsonb | required — the numbers backing `reason` |
| risk | text | required — what could go wrong |
| expected_benefit | text | required |
| confidence | numeric(3,2) | 0–1, model-reported |
| status | enum(`open`,`accepted`,`dismissed`,`superseded`) | |
| generated_by_agent | text | e.g. `recommendation_agent_v1` |

### `goals`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| type | enum(`retirement`,`house`,`education`,`emergency_fund`,`fire`,`vacation`,`wealth_creation`) | |
| target_amount | numeric(16,2) | |
| target_date | date | |
| current_progress_value | numeric(16,2) | |
| required_monthly_sip | numeric(12,2) | computed |
| assumed_return_rate | numeric(5,2) | % p.a., used in projection |
| probability_of_success | numeric(5,2) | Monte-Carlo based, % |

### `goal_projections` (Monte Carlo run outputs, for charting the fan)
| column | type | notes |
|---|---|---|
| goal_id | uuid fk | |
| percentile | int | 10/25/50/75/90 |
| projected_value_by_year | jsonb | `{2026: x, 2027: y, ...}` |

### `tax_records`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| portfolio_id | uuid fk | |
| financial_year | text | e.g. `2025-26` |
| ltcg | numeric(14,2) | |
| stcg | numeric(14,2) | |
| ltcg_tax | numeric(14,2) | |
| stcg_tax | numeric(14,2) | |
| harvesting_opportunities | jsonb | `[{holding_id, unrealized_gain, action, tax_saved}]` |

### `alerts`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk | |
| portfolio_id | uuid fk nullable | |
| type | enum(`underperformance`,`expense_ratio_change`,`manager_change`,`overlap_increase`,`exit_load_ended`,`tax_harvest`,`market_crash`,`sebi_circular`) | |
| severity | enum(`info`,`warning`,`critical`) | |
| title | text | |
| body | text | |
| channels_sent | jsonb | `{email: true, whatsapp: false, push: true}` |
| read_at | timestamptz nullable | |

### `chat_sessions` / `chat_messages`
Standard conversation history keyed by `user_id` + `portfolio_id`, with
`chat_messages.tool_calls jsonb` capturing which agents/tools were invoked to
answer, so answers can cite their evidence.

### `import_jobs` / `import_rows`
Tracks each uploaded statement: `source_type`, `s3_key`, `status`
(`pending`,`parsing`,`parsed`,`failed`,`needs_review`), `error_detail`, plus
one `import_rows` row per parsed transaction for auditability/debugging
before it is committed into `transactions`.

### `audit_logs`
Append-only: `actor_user_id`, `organization_id`, `action`, `entity_type`,
`entity_id`, `diff jsonb`, `ip_address`, `created_at`. Required for
GDPR/financial-audit compliance; never updated or deleted (retention policy
handled by lifecycle archival to S3 Glacier, not deletion).

## Vector store (pgvector)

`fund_documents` (factsheets, SEBI circulars, AMC news) and
`kb_chunks(embedding vector(3072), source, metadata jsonb)` back the Fund
Research and News Intelligence agents' RAG retrieval — see
`AI_AGENT_WORKFLOW.md §4`.

## Migrations

Managed with Alembic (`apps/api/alembic/`). `alembic revision --autogenerate`
against the SQLAlchemy models in `apps/api/app/models/`, reviewed by hand
before merge (autogenerate does not detect RLS policies or enum value
additions safely — those ship as explicit migration files).
