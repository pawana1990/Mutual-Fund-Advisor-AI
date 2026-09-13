"""Portfolio Analysis Agent — no LLM call. Computes XIRR, CAGR-equivalent
returns, allocation breakdowns, and concentration flags from raw holdings.
Pure/deterministic by design (see docs/AI_AGENT_WORKFLOW.md §3)."""
from __future__ import annotations

from datetime import date

from app.agents.state import AdvisorState, HoldingView, PortfolioMetrics
from app.services.financial_metrics import (
    CashFlow,
    FinancialMetricsError,
    allocation_breakdown,
    concentration_risk_flag,
    xirr,
)

AGENT_NAME = "portfolio_analysis_agent_v1"


def run(state: AdvisorState) -> dict:
    holdings: list[HoldingView] = state.get("holdings", [])
    if not holdings:
        return {
            "portfolio_metrics": PortfolioMetrics(
                invested_value=0.0, current_value=0.0, xirr=0.0, absolute_return_pct=0.0,
                asset_allocation={}, sector_allocation={}, amc_allocation={}, concentration_flags=[],
            )
        }

    invested_value = sum(h["invested_value"] for h in holdings)
    current_value = sum(h["current_value"] for h in holdings)

    # Approximate portfolio XIRR from each holding's invested-vs-current
    # value using its earliest lot date as the single outflow date — a
    # simplification the real implementation refines with full transaction
    # history (see services/financial_metrics.xirr + Transaction model).
    cashflows = []
    for h in holdings:
        try:
            buy_date = date.fromisoformat(h["buy_date"])
        except (KeyError, ValueError):
            continue
        if h["invested_value"] > 0:
            cashflows.append(CashFlow(buy_date, -h["invested_value"]))
    if current_value > 0:
        cashflows.append(CashFlow(date.today(), current_value))

    try:
        portfolio_xirr = xirr(cashflows) if len(cashflows) >= 2 else 0.0
    except FinancialMetricsError:
        portfolio_xirr = 0.0

    absolute_return_pct = (
        round((current_value - invested_value) / invested_value * 100, 2) if invested_value > 0 else 0.0
    )

    fund_values = {h["fund_id"]: h["current_value"] for h in holdings}
    amc_values: dict[str, float] = {}
    category_values: dict[str, float] = {}
    for h in holdings:
        amc_values[h["amc"]] = amc_values.get(h["amc"], 0.0) + h["current_value"]
        category_values[h["category"]] = category_values.get(h["category"], 0.0) + h["current_value"]

    equity_categories = {"Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Multi Cap", "ELSS", "Sectoral"}
    asset_values: dict[str, float] = {}
    for h in holdings:
        bucket = "equity" if h["category"] in equity_categories else "debt"
        asset_values[bucket] = asset_values.get(bucket, 0.0) + h["current_value"]

    fund_name_by_id = {h["fund_id"]: h["fund_name"] for h in holdings}
    concentration_flags = [
        fund_name_by_id.get(fid, fid) for fid in concentration_risk_flag(fund_values, threshold_pct=25.0)
    ] if fund_values else []

    metrics = PortfolioMetrics(
        invested_value=round(invested_value, 2),
        current_value=round(current_value, 2),
        xirr=round(portfolio_xirr * 100, 2),
        absolute_return_pct=absolute_return_pct,
        asset_allocation=allocation_breakdown(asset_values) if asset_values else {},
        sector_allocation=allocation_breakdown(category_values) if category_values else {},
        amc_allocation=allocation_breakdown(amc_values) if amc_values else {},
        concentration_flags=concentration_flags,
    )
    return {"portfolio_metrics": metrics}
