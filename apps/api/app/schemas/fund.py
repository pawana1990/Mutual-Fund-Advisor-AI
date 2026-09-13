from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class FundSearchResult(BaseModel):
    id: UUID
    isin: str
    name: str
    amc: str
    category: str
    current_nav: str | None


class FundDetailOut(BaseModel):
    id: UUID
    isin: str
    name: str
    amc: str
    category: str
    sub_category: str | None
    benchmark: str | None
    fund_manager: str | None
    expense_ratio: str | None
    aum_cr: str | None
    inception_date: date | None
    current_nav: str | None
    current_nav_date: date | None


class FundRiskMetricsOut(BaseModel):
    window: str
    cagr: float | None
    beta: float | None
    alpha: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    std_deviation: float | None
    max_drawdown: float | None
    category_rank: int | None
    category_size: int | None


class FundComparisonOut(BaseModel):
    funds: list[FundDetailOut]
    risk_metrics: dict[str, FundRiskMetricsOut]
