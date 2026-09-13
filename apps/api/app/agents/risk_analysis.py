"""Risk Analysis Agent — aggregates per-fund risk metrics (already computed
nightly by the fund-data pipeline into `fund_metrics`) into portfolio-level
figures, and asks the LLM ONLY to explain them in plain English. The LLM
never computes a number here (see docs/AI_AGENT_WORKFLOW.md §3)."""
from __future__ import annotations

from app.agents.llm import ChatModel, get_chat_model
from app.agents.state import AdvisorState

AGENT_NAME = "risk_analysis_agent_v1"

_METRIC_EXPLANATIONS = {
    "beta": "how much your portfolio tends to move relative to the market — 1.0 means it moves in line with the market, above 1.0 means bigger swings than the market",
    "alpha": "the extra return (or shortfall) versus what you'd expect given the risk taken, after accounting for the market's move",
    "sharpe_ratio": "return earned per unit of total risk taken — higher is better; below 0.5 is generally considered weak",
    "sortino_ratio": "like the Sharpe ratio but only penalizes downside swings, not the upside volatility that investors don't mind",
    "std_deviation": "how much your portfolio's returns bounce around its own average — higher means a bumpier ride",
    "max_drawdown": "the worst peak-to-trough fall your portfolio has experienced — a measure of how bad the worst period would have felt",
}


def _weighted_average(holdings: list[dict], fund_metrics: dict[str, dict], key: str) -> float | None:
    total_value = sum(h["current_value"] for h in holdings)
    if total_value <= 0:
        return None
    weighted_sum = 0.0
    covered_value = 0.0
    for h in holdings:
        metrics = fund_metrics.get(h["fund_id"], {})
        value = metrics.get(key)
        if value is None:
            continue
        weighted_sum += value * h["current_value"]
        covered_value += h["current_value"]
    if covered_value == 0:
        return None
    return weighted_sum / covered_value


def run(state: AdvisorState, *, chat_model: ChatModel | None = None) -> dict:
    holdings = state.get("holdings", [])
    fund_metrics = state.get("fund_metrics", {})

    if not holdings:
        return {"risk_report": {"metrics": {}, "explanations": {}}}

    metrics = {
        key: round(value, 4)
        for key in ("beta", "alpha", "sharpe_ratio", "sortino_ratio", "std_deviation", "max_drawdown")
        if (value := _weighted_average(holdings, fund_metrics, key)) is not None
    }

    model = chat_model or get_chat_model()
    explanations: dict[str, str] = {}
    for key, value in metrics.items():
        base_explanation = _METRIC_EXPLANATIONS.get(key, "")
        prompt = (
            f"Your portfolio's {key.replace('_', ' ')} is {value}. "
            f"In one or two plain-English sentences (no jargon), explain what this figure of {value} means "
            f"for this investor, given that {key.replace('_', ' ')} measures {base_explanation}. "
            "Do not invent any numbers other than the one given."
        )
        try:
            explanations[key] = model.complete(
                system="You are a financial-risk explainer. You only ever explain numbers you are given; you never invent new ones.",
                user=prompt,
            )
        except Exception:
            explanations[key] = f"Your {key.replace('_', ' ')} is {value}: {base_explanation}."

    return {"risk_report": {"metrics": metrics, "explanations": explanations}}
