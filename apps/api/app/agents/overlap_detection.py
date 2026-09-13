"""Overlap Detection Agent — thin wrapper around the deterministic
`services/overlap.py` engine. Expects `state["fund_baskets"]` (a mapping of
fund_id -> underlying stock/sector weights, sourced from the Fund Research
Agent's factsheet ingestion) to already be populated."""
from __future__ import annotations

from dataclasses import asdict

from app.agents.state import AdvisorState
from app.services.overlap import FundStockBasket, build_overlap_report

AGENT_NAME = "overlap_detection_agent_v1"


def run(state: AdvisorState) -> dict:
    holdings = state.get("holdings", [])
    fund_baskets_raw: dict = state.get("fund_baskets", {})  # type: ignore[assignment]

    if not holdings or not fund_baskets_raw:
        return {"overlap_report": {}}

    baskets = []
    holding_values: dict[str, float] = {}
    for h in holdings:
        fund_id = h["fund_id"]
        holding_values[fund_id] = holding_values.get(fund_id, 0.0) + h["current_value"]
        raw = fund_baskets_raw.get(fund_id)
        if raw is None:
            continue
        baskets.append(
            FundStockBasket(
                fund_id=fund_id,
                fund_name=h["fund_name"],
                amc=h["amc"],
                stock_weights=raw.get("stock_weights", {}),
                sector_weights=raw.get("sector_weights", {}),
            )
        )

    if len(baskets) < 1:
        return {"overlap_report": {}}

    report = build_overlap_report(baskets, holding_values)
    return {
        "overlap_report": {
            "portfolio_overlap_pct": report.portfolio_overlap_pct,
            "duplicate_pairs": [asdict(p) for p in report.duplicate_pairs],
            "amc_concentration": report.amc_concentration,
            "sector_overlap": report.sector_overlap,
            "amc_hhi": report.amc_hhi,
        }
    }
