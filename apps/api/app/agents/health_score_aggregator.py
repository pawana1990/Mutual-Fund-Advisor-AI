"""Health Score Aggregator — deterministic node (no LLM) that combines the
outputs of every upstream agent into the 0-100 Portfolio Health Score. The
LLM is used only afterward, in `explain_health_score`, to narrate the
already-computed sub-scores — never to compute them."""
from __future__ import annotations

from app.agents.llm import ChatModel, get_chat_model
from app.agents.state import AdvisorState
from app.services.health_score import HealthScoreInputs, compute_health_score

AGENT_NAME = "health_score_aggregator_v1"

_RISK_PROFILE_VOL_TOLERANCE = {"conservative": 8.0, "moderate": 14.0, "aggressive": 22.0}
_RISK_PROFILE_TARGET_EQUITY = {"conservative": 30.0, "moderate": 60.0, "aggressive": 85.0}


def run(state: AdvisorState, *, risk_profile: str = "moderate") -> dict:
    portfolio_metrics = state.get("portfolio_metrics", {})
    risk_report = state.get("risk_report", {})
    tax_report = state.get("tax_report", {})
    goals = state.get("goals", [])
    holdings = state.get("holdings", [])
    fund_metrics = state.get("fund_metrics", {})

    if not holdings:
        return {"health_score": {}}

    amc_values: dict[str, float] = {}
    sector_values: dict[str, float] = {}
    for h in holdings:
        amc_values[h["amc"]] = amc_values.get(h["amc"], 0.0) + h["current_value"]
        sector_values[h["category"]] = sector_values.get(h["category"], 0.0) + h["current_value"]

    weighted_expense_ratio = sum(
        h["expense_ratio"] * h["current_value"] for h in holdings
    ) / max(sum(h["current_value"] for h in holdings), 1e-6)
    category_median_expense = sum(
        fund_metrics.get(h["fund_id"], {}).get("category_median_expense_ratio", h["expense_ratio"])
        for h in holdings
    ) / len(holdings)

    avg_rank_percentile = sum(
        100 * (1 - m["category_rank"] / m["category_size"])
        if (m := fund_metrics.get(h["fund_id"], {})).get("category_rank") and m.get("category_size")
        else 50.0
        for h in holdings
    ) / len(holdings)

    equity_pct = portfolio_metrics.get("asset_allocation", {}).get("equity", 0.0)

    inputs = HealthScoreInputs(
        amc_values=amc_values,
        sector_values=sector_values,
        fund_count=len(holdings),
        portfolio_volatility_pct=risk_report.get("metrics", {}).get("std_deviation", 15.0),
        portfolio_max_drawdown_pct=risk_report.get("metrics", {}).get("max_drawdown", -20.0) * 100
        if abs(risk_report.get("metrics", {}).get("max_drawdown", -0.2)) <= 1
        else risk_report.get("metrics", {}).get("max_drawdown", -20.0),
        risk_profile_volatility_tolerance_pct=_RISK_PROFILE_VOL_TOLERANCE.get(risk_profile, 14.0),
        portfolio_xirr_pct=portfolio_metrics.get("xirr", 0.0),
        category_median_xirr_pct=sum(
            fund_metrics.get(h["fund_id"], {}).get("category_median_xirr", portfolio_metrics.get("xirr", 0.0))
            for h in holdings
        ) / len(holdings),
        weighted_avg_expense_ratio_pct=weighted_expense_ratio,
        category_median_expense_ratio_pct=category_median_expense,
        avg_category_rank_percentile=avg_rank_percentile,
        unrealized_ltcg_within_exemption_pct=100.0
        if not tax_report.get("harvesting_opportunities")
        else 60.0,
        stcg_pct_of_total_gains=20.0,
        equity_pct=equity_pct,
        target_equity_pct=_RISK_PROFILE_TARGET_EQUITY.get(risk_profile, 60.0),
        avg_goal_probability_of_success_pct=(
            sum(g.get("probability_of_success", 70.0) for g in goals) / len(goals) if goals else 70.0
        ),
    )

    result = compute_health_score(inputs)
    return {
        "health_score": {
            "overall_score": result.overall_score,
            "diversification_score": result.diversification_score,
            "risk_score": result.risk_score,
            "returns_score": result.returns_score,
            "fees_score": result.fees_score,
            "fund_quality_score": result.fund_quality_score,
            "tax_efficiency_score": result.tax_efficiency_score,
            "asset_allocation_score": result.asset_allocation_score,
            "goal_readiness_score": result.goal_readiness_score,
        }
    }


def explain_health_score(health_score: dict, *, chat_model: ChatModel | None = None) -> str:
    if not health_score:
        return "Not enough data yet to compute a Portfolio Health Score."
    model = chat_model or get_chat_model()
    return model.complete(
        system=(
            "Explain this investor's Portfolio Health Score in 3-4 plain-English sentences, referencing "
            "only the sub-scores given, calling out the single lowest sub-score as the priority to improve."
        ),
        user=f"Health score breakdown: {health_score}",
    )
