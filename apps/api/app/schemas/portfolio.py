"""Pydantic request/response schemas for the portfolio, funds, risk,
recommendation, goal, and tax endpoints — see docs/API_DESIGN.md."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, default="Primary")
    base_currency: str = Field(default="INR", min_length=3, max_length=3)


class PortfolioOut(BaseModel):
    id: UUID
    name: str
    base_currency: str
    owner_user_id: UUID

    model_config = {"from_attributes": True}


class HoldingOut(BaseModel):
    id: UUID
    fund_id: UUID
    fund_name: str
    amc: str
    category: str
    units: str  # money-safe string wire format
    avg_cost_nav: str
    invested_value: str
    current_value: str
    unrealized_gain: str
    unrealized_gain_pct: str


class SnapshotOut(BaseModel):
    as_of: datetime
    invested_value: str
    current_value: str
    xirr: str
    absolute_return_pct: str
    asset_allocation: dict[str, float]
    sector_allocation: dict[str, float]
    amc_allocation: dict[str, float]
    top_holdings: list[dict]


class HealthScoreOut(BaseModel):
    overall_score: int
    diversification_score: int
    risk_score: int
    returns_score: int
    fees_score: int
    fund_quality_score: int
    tax_efficiency_score: int
    asset_allocation_score: int
    goal_readiness_score: int
    explanation: str


class RiskMetricOut(BaseModel):
    value: float
    explanation: str


class RiskReportOut(BaseModel):
    beta: RiskMetricOut | None = None
    alpha: RiskMetricOut | None = None
    sharpe_ratio: RiskMetricOut | None = None
    sortino_ratio: RiskMetricOut | None = None
    std_deviation: RiskMetricOut | None = None
    max_drawdown: RiskMetricOut | None = None


class RecommendationOut(BaseModel):
    id: UUID
    holding_id: UUID | None
    action: str
    switch_target_fund_id: UUID | None
    reason: str
    supporting_metrics: dict
    risk: str
    expected_benefit: str
    confidence: float
    status: str
    generated_by_agent: str


class RecommendationFeedback(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class GoalCreate(BaseModel):
    type: str
    target_amount: float = Field(gt=0)
    target_date: date
    assumed_return_rate: float = Field(default=11.0, ge=0, le=30)
    step_up_pct_per_year: float = Field(default=0.0, ge=0, le=50)


class GoalOut(BaseModel):
    id: UUID
    type: str
    target_amount: str
    target_date: date
    required_monthly_sip: str | None
    probability_of_success: float | None


class GoalProjectionOut(BaseModel):
    percentiles: dict[int, dict[int, float]]
    required_monthly_sip: str
    probability_of_success: float


class TaxSummaryOut(BaseModel):
    financial_year: str
    ltcg: str
    stcg: str
    ltcg_tax: str
    stcg_tax: str
    total_tax: str


class HarvestingOpportunityOut(BaseModel):
    holding_id: UUID
    fund_name: str
    unrealized_gain: str
    recommended_action: str
    estimated_tax_saved: str
    reason: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    citations: dict = Field(default_factory=dict)
