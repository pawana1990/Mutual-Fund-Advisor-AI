"""Shared DB -> `HoldingView` mapping, used by every router/agent-invoking
endpoint that needs to build `AdvisorState["holdings"]` from the database."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import HoldingView
from app.models.fund import Fund
from app.models.portfolio import Holding

_EQUITY_CATEGORIES = {"Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Multi Cap", "ELSS"}


async def load_holding_views(session: AsyncSession, portfolio_id: UUID) -> list[HoldingView]:
    stmt = (
        select(Holding, Fund)
        .join(Fund, Fund.id == Holding.fund_id)
        .where(Holding.portfolio_id == portfolio_id)
    )
    result = await session.execute(stmt)
    views: list[HoldingView] = []
    for holding, fund in result.all():
        views.append(
            HoldingView(
                holding_id=str(holding.id),
                fund_id=str(fund.id),
                fund_name=fund.name,
                amc=fund.amc,
                category=fund.category,
                asset_type="equity" if fund.category in _EQUITY_CATEGORIES else "debt",
                units=float(holding.units),
                invested_value=float(holding.invested_value),
                current_value=float(holding.current_value),
                avg_cost_nav=float(holding.avg_cost_nav),
                current_nav=float(fund.current_nav or holding.avg_cost_nav),
                expense_ratio=float(fund.expense_ratio or 0.0),
                buy_date=str(holding.created_at.date()),
            )
        )
    return views
