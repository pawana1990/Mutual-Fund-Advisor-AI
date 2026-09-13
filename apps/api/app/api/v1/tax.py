"""Tax endpoints, nested under a portfolio — see docs/API_DESIGN.md `Tax`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tax_agent import run as run_tax_agent
from app.api.v1.deps import get_owned_portfolio, get_tenant_session
from app.models.portfolio import Portfolio
from app.schemas.portfolio import HarvestingOpportunityOut, TaxSummaryOut
from app.services.holding_view import load_holding_views

router = APIRouter()


@router.get("/portfolios/{portfolio_id}/tax", response_model=TaxSummaryOut)
async def get_tax_summary(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
    fy: str | None = Query(default=None, description="e.g. 2025-26"),
) -> TaxSummaryOut:
    holdings = await load_holding_views(session, portfolio.id)
    result = run_tax_agent({"holdings": holdings})
    report = result["tax_report"]
    # LTCG/STCG realized-gain aggregation happens from the Transaction ledger
    # in the full implementation; harvesting opportunities (unrealized) are
    # always computed live from current holdings, as shown here.
    total_saving = report.get("total_potential_tax_saving", 0.0)
    return TaxSummaryOut(
        financial_year=fy or report["financial_year"],
        ltcg="0.00", stcg="0.00", ltcg_tax="0.00", stcg_tax="0.00",
        total_tax=f"{total_saving:.2f}",
    )


@router.get(
    "/portfolios/{portfolio_id}/tax/harvesting-opportunities",
    response_model=list[HarvestingOpportunityOut],
)
async def get_harvesting_opportunities(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[HarvestingOpportunityOut]:
    holdings = await load_holding_views(session, portfolio.id)
    result = run_tax_agent({"holdings": holdings})
    return [
        HarvestingOpportunityOut(
            holding_id=o["holding_id"], fund_name=o["fund_name"],
            unrealized_gain=f"{o['unrealized_gain']:.2f}",
            recommended_action=o["recommended_action"],
            estimated_tax_saved=f"{o['estimated_tax_saved']:.2f}",
            reason=o["reason"],
        )
        for o in result["tax_report"]["harvesting_opportunities"]
    ]
