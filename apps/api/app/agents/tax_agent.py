"""Tax Agent — wraps `services/tax_calculator.py`. Computes LTCG/STCG for the
current financial year from holdings' unrealized position (used for
"what-if I sell today" style chat questions) and surfaces harvesting
opportunities."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.agents.state import AdvisorState
from app.services.tax_calculator import FundAssetType, find_tax_harvesting_opportunities

AGENT_NAME = "tax_agent_v1"


def _current_financial_year(today: date | None = None) -> str:
    today = today or date.today()
    if today.month >= 4:
        return f"{today.year}-{str(today.year + 1)[-2:]}"
    return f"{today.year - 1}-{str(today.year)[-2:]}"


def run(state: AdvisorState) -> dict:
    holdings = state.get("holdings", [])
    if not holdings:
        return {"tax_report": {"financial_year": _current_financial_year(), "harvesting_opportunities": []}}

    harvest_candidates = [
        {
            "holding_id": h["holding_id"],
            "fund_name": h["fund_name"],
            "asset_type": h.get("asset_type", FundAssetType.EQUITY.value),
            "buy_date": date.fromisoformat(h["buy_date"]) if h.get("buy_date") else date.today(),
            "buy_nav": h["avg_cost_nav"],
            "current_nav": h["current_nav"],
            "units": h["units"],
        }
        for h in holdings
    ]

    opportunities = find_tax_harvesting_opportunities(harvest_candidates)
    total_potential_saving = sum(o.estimated_tax_saved for o in opportunities)

    return {
        "tax_report": {
            "financial_year": _current_financial_year(),
            "harvesting_opportunities": [asdict(o) for o in opportunities],
            "total_potential_tax_saving": round(total_potential_saving, 2),
        }
    }
