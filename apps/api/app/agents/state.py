"""The shared `AdvisorState` threaded through the LangGraph supervisor graph.

Every agent node is a pure function `(state: AdvisorState) -> dict` that
returns ONLY the keys it patches — see docs/AI_AGENT_WORKFLOW.md §1. This
makes every agent unit-testable with a plain dict and no live LLM/DB.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _last_write_wins(existing: Any, new: Any) -> Any:
    return new


def _append(existing: list | None, new: list) -> list:
    return (existing or []) + new


class HoldingView(TypedDict):
    holding_id: str
    fund_id: str
    fund_name: str
    amc: str
    category: str
    asset_type: str  # equity | debt | hybrid_equity_oriented | hybrid_debt_oriented
    units: float
    invested_value: float
    current_value: float
    avg_cost_nav: float
    current_nav: float
    expense_ratio: float
    buy_date: str  # ISO date of the earliest lot, used for tax-term checks


class FundMetrics(TypedDict, total=False):
    fund_id: str
    window: str
    cagr: float
    beta: float
    alpha: float
    sharpe_ratio: float
    sortino_ratio: float
    std_deviation: float
    max_drawdown: float
    category_rank: int
    category_size: int
    category_median_expense_ratio: float
    category_median_xirr: float


class PortfolioMetrics(TypedDict, total=False):
    invested_value: float
    current_value: float
    xirr: float
    absolute_return_pct: float
    asset_allocation: dict[str, float]
    sector_allocation: dict[str, float]
    amc_allocation: dict[str, float]
    concentration_flags: list[str]


class Recommendation(TypedDict):
    holding_id: str | None
    action: str  # keep | increase | reduce | exit | switch
    switch_target_fund_id: str | None
    reason: str
    supporting_metrics: dict[str, Any]
    risk: str
    expected_benefit: str
    confidence: float
    generated_by_agent: str


class AgentError(TypedDict):
    agent: str
    message: str


class AdvisorState(TypedDict, total=False):
    portfolio_id: str
    holdings: list[HoldingView]
    fund_metrics: dict[str, FundMetrics]  # fund_id -> metrics
    portfolio_metrics: PortfolioMetrics
    overlap_report: dict[str, Any]
    risk_report: dict[str, Any]
    tax_report: dict[str, Any]
    recommendations: Annotated[list[Recommendation], _append]
    goals: list[dict[str, Any]]
    news_signals: list[dict[str, Any]]
    health_score: dict[str, Any]
    chat_question: str | None
    chat_intent: str | None
    chat_answer: dict[str, Any] | None
    errors: Annotated[list[AgentError], _append]
