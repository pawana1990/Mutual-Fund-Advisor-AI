# AI Agent Workflow (LangGraph)

## 1. Shared state

All agents read/write a single typed `AdvisorState` (TypedDict/Pydantic model,
`apps/api/app/agents/state.py`) threaded through the graph:

```python
class AdvisorState(TypedDict, total=False):
    portfolio_id: str
    holdings: list[HoldingView]
    transactions: list[TransactionView]
    fund_metrics: dict[str, FundMetrics]      # fund_id -> latest metrics
    portfolio_metrics: PortfolioMetrics        # XIRR, CAGR, allocation
    overlap_report: OverlapReport
    risk_report: RiskReport
    recommendations: list[Recommendation]
    goals: list[GoalProjection]
    tax_report: TaxReport
    news_signals: list[NewsSignal]
    health_score: HealthScore
    chat_question: str | None
    chat_answer: ChatAnswer | None
    errors: list[AgentError]
```

Every node is a pure function `def run(state) -> dict` returning only the
keys it patches — this makes each agent independently unit-testable with a
plain dict, no LLM or DB required (see `apps/api/app/tests/agents/`).

## 2. Graph topology

```
                       ┌────────────────────┐
                       │   Load Portfolio     │  (DB fetch, no LLM)
                       └──────────┬───────────┘
                                   │
                       ┌──────────▼───────────┐
                       │ Portfolio Analysis    │  XIRR/CAGR/allocation/concentration
                       │ Agent                 │
                       └──────────┬───────────┘
                                   │  fan-out (parallel branches)
        ┌───────────────┬─────────┴─────────┬───────────────────┐
┌───────▼──────┐ ┌───────▼───────┐  ┌────────▼────────┐  ┌───────▼───────┐
│ Fund Research │ │ Overlap        │  │ Risk Analysis    │  │ Tax Agent      │
│ Agent          │ │ Detection Agent│  │ Agent            │  │                │
└───────┬──────┘ └───────┬───────┘  └────────┬────────┘  └───────┬───────┘
        └───────────────┬┴────────────────────┴───────────────────┘
                       ┌──▼───────────────┐
                       │ Recommendation    │  synthesizes all upstream reports
                       │ Agent             │  into Keep/Increase/Reduce/Exit/Switch
                       └──────────┬───────┘
                                   │
                       ┌──────────▼───────────┐
                       │ Goal Planning Agent   │  (reads recs + metrics, Monte Carlo)
                       └──────────┬───────────┘
                                   │
                       ┌──────────▼───────────┐
                       │ Health Score          │  deterministic aggregator (no LLM)
                       │ Aggregator            │
                       └──────────┬───────────┘
                                   │
                       ┌──────────▼───────────┐
                       │ Persist + Notify      │
                       └──────────────────────┘

  News Intelligence Agent runs on its own scheduled trigger (not per-request),
  writing `news_signals` + `alerts` that the Recommendation Agent reads on its
  next run.
```

`apps/api/app/agents/orchestrator.py` builds this with LangGraph's
`StateGraph`, using `add_conditional_edges` so a **chat** request only routes
through the specific agents needed to answer the question (a supervisor
"router" node classifies intent — e.g. "Should I exit Axis Bluechip?" routes
to `fund_research → risk_analysis → recommendation`, while "Will I reach ₹5
crore?" routes straight to `goal_planning`) instead of always re-running the
full pipeline synchronously.

## 3. Agent contracts

| Agent | Inputs | Outputs | LLM used for | Deterministic core |
|---|---|---|---|---|
| Portfolio Analysis | transactions, holdings | XIRR, CAGR, allocation, concentration | — | `services/financial_metrics.py` (pure math, no LLM) |
| Fund Research | fund_id(s) | NAV, expense ratio, manager, AUM, benchmark, category rank, rolling returns | summarizing factsheet PDFs via RAG | data fetched from `fund_nav_history`/`fund_risk_metrics` tables, refreshed by a scheduled AMFI/provider sync job |
| Overlap Detection | holdings (underlying stock baskets) | overlap %, duplicate pairs, AMC/sector concentration | explaining the overlap in plain English | `services/overlap.py` — set-intersection/Jaccard over each fund's top holdings |
| Risk Analysis | returns series (fund + benchmark + risk-free) | beta, alpha, Sharpe, Sortino, volatility, std dev, max drawdown + plain-English explanation of each | explanation only, never the numbers | `services/financial_metrics.py` |
| Recommendation | all upstream reports | `{action, reason, supporting_metrics, risk, expected_benefit, confidence}` per holding | synthesis + natural-language reasoning, **grounded**: the prompt template forces the model to cite fields from `supporting_metrics` it was given, and a post-hoc validator rejects any recommendation whose `reason` references a number not present in `supporting_metrics` | ranking/thresholds pre-computed in `services/recommendation_rules.py` (e.g. expense ratio > category median + 2 std dev ⇒ candidate for `switch`) |
| Goal Planning | goals, portfolio_metrics | required monthly SIP, probability of success | explaining trade-offs | `services/goal_planning.py` — closed-form annuity math + Monte Carlo (numpy) for the probability fan |
| Tax Agent | transactions, current NAV | LTCG/STCG, exit load, harvesting opportunities | explaining tax impact of a hypothetical sell | `services/tax_calculator.py` — codified Indian equity/debt MF tax rules (see file for the exact slabs; kept in one file so a tax-law change is a one-file diff) |
| News Intelligence | AMC/fund watchlist | manager changes, expense ratio changes, SEBI circulars, market events | summarization + relevance classification via RAG over `kb_chunks` | scheduled job, not per-request |

## 4. Grounding & guardrails (never recommend without evidence)

1. **Evidence-first prompting**: the LLM is given a JSON blob of
   `supporting_metrics` and instructed: *"Only reference numbers present in
   the JSON below. If you cannot justify an action from these numbers, choose
   `keep` and explain what additional data is needed."*
2. **Post-generation validator** (`agents/guardrails.py`): regex/number
   extraction on the model's `reason` string, cross-checked against
   `supporting_metrics` values (with tolerance for rounding/formatting) —
   recommendations failing validation are downgraded to `keep` and logged for
   human/prompt-engineering review, never shown to the user as-is.
3. **No execution capability.** Agents never place trades; `POST
   /recommendations/{id}/accept` only records user intent, consistent with
   SEBI's investment-adviser vs. execution-only distinction — actual
   execution stays with the user's broker/RTA.
4. **Confidence + abstention.** Every recommendation carries a `confidence`
   (0–1); anything below a configurable threshold (default 0.55) is surfaced
   as an "insight" rather than an actionable recommendation in the UI.
5. **Model+prompt versioning.** `generated_by_agent` stores an agent+prompt
   version string so a bad prompt rollout can be identified and all its
   recommendations bulk-superseded.

## 5. RAG pipeline (Fund Research + News Intelligence)

Factsheets, SEBI circulars and AMC news are chunked (semantic, ~500 tokens),
embedded with `OPENAI_EMBEDDING_MODEL`, and stored in `kb_chunks
(embedding vector(3072))`. Retrieval uses pgvector cosine similarity
(`<=>`) filtered by `fund_id`/`amc` metadata before the LLM call — never an
unfiltered global similarity search, to avoid cross-fund hallucination.

## 6. Observability for agents

Every agent invocation logs: input state hash, prompt+model version, token
usage, latency, and (if validation failed) the rejected output — to
CloudWatch + a `agent_runs` table, powering the Grafana "AI Ops" dashboard
(cost per portfolio-refresh, validator rejection rate, p95 latency per
agent) described in `MONITORING.md`.
