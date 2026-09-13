"""Recommendation Agent — synthesizes Portfolio/Overlap/Risk/Tax agent
outputs into per-holding Keep/Increase/Reduce/Exit/Switch recommendations.

Pipeline per holding (see docs/AI_AGENT_WORKFLOW.md §4):
  1. `services.recommendation_rules.evaluate_holding` decides the *action*
     deterministically from thresholds — the LLM never picks the action.
  2. The LLM is given ONLY `supporting_metrics` and asked to write `reason`,
     `risk`, `expected_benefit` — instructed to cite only those numbers.
  3. `agents.guardrails.enforce_guardrails` validates the LLM's text against
     the metrics it was given, downgrading to `keep` on any violation.
"""
from __future__ import annotations

import json

from app.agents.guardrails import enforce_guardrails
from app.agents.llm import ChatModel, get_chat_model
from app.agents.state import AdvisorState
from app.core.config import get_settings
from app.services.recommendation_rules import evaluate_holding

AGENT_NAME = "recommendation_agent_v1"

_SYSTEM_PROMPT = (
    "You are a Certified Financial Planner explaining a mutual-fund recommendation to a retail "
    "investor. You will be given a decided ACTION and a JSON object of SUPPORTING_METRICS. "
    "You must return a JSON object with exactly three string fields: "
    '{"reason": "...", "risk": "...", "expected_benefit": "..."}. '
    "Rules: (1) Only reference numbers that appear in SUPPORTING_METRICS — never invent a number. "
    "(2) `reason` must explain WHY the action follows from those numbers. "
    "(3) `risk` must explain what could go wrong with taking this action. "
    "(4) `expected_benefit` must explain the concrete upside if the action plays out as expected. "
    "(5) Plain English, no jargon without a one-clause explanation."
)


def _narrate(model: ChatModel, action: str, metrics: dict) -> dict:
    user_prompt = f"ACTION: {action}\nSUPPORTING_METRICS: {json.dumps(metrics)}"
    try:
        raw = model.complete(system=_SYSTEM_PROMPT, user=user_prompt)
    except Exception:
        # LLM outage/network/auth failure: degrade to a template-generated
        # explanation rather than 500ing the whole recompute pipeline — the
        # numeric dashboard and rule-derived action must never depend on the
        # LLM being reachable. See docs/MONITORING.md "OpenAI API outage".
        return _template_narration(action, metrics)

    try:
        parsed = json.loads(raw)
        return {
            "reason": str(parsed.get("reason", "")),
            "risk": str(parsed.get("risk", "")),
            "expected_benefit": str(parsed.get("expected_benefit", "")),
        }
    except (json.JSONDecodeError, AttributeError):
        # Fall back to a template-generated explanation rather than dropping
        # the recommendation entirely if the LLM misformats its output.
        return _template_narration(action, metrics)


def _template_narration(action: str, metrics: dict) -> dict:
    verb = {
        "exit": "exit this fund",
        "switch": "switch out of this fund into a comparable, better-performing alternative",
        "reduce": "reduce your allocation to this fund",
        "increase": "increase your allocation to this fund",
        "keep": "keep this fund as-is",
    }.get(action, "keep this fund as-is")
    metric_str = ", ".join(f"{k.replace('_', ' ')} = {v}" for k, v in metrics.items())
    return {
        "reason": f"Based on {metric_str}, the analysis suggests you {verb}.",
        "risk": "Market conditions and fund performance can change; past metrics do not guarantee future results.",
        "expected_benefit": "Aligning your holding with the evidence above supports better risk-adjusted, long-term outcomes.",
    }


def run(state: AdvisorState, *, chat_model: ChatModel | None = None) -> dict:
    holdings = state.get("holdings", [])
    fund_metrics = state.get("fund_metrics", {})
    overlap_report = state.get("overlap_report", {})
    settings = get_settings()

    if not holdings:
        return {"recommendations": []}

    model = chat_model or get_chat_model()
    duplicate_pairs = {
        (p["fund_a"], p["fund_b"]): p["overlap_pct"] for p in overlap_report.get("duplicate_pairs", [])
    }
    concentration_pct_by_fund = {}
    total_value = sum(h["current_value"] for h in holdings) or 1.0
    for h in holdings:
        concentration_pct_by_fund[h["fund_id"]] = h["current_value"] / total_value * 100

    recommendations = []
    for h in holdings:
        m = fund_metrics.get(h["fund_id"], {})
        overlap_pct = max(
            [pct for (a, b), pct in duplicate_pairs.items() if h["fund_id"] in (a, b)], default=0.0
        )

        verdict = evaluate_holding(
            expense_ratio=h.get("expense_ratio", 0.0),
            category_median_expense_ratio=m.get("category_median_expense_ratio", h.get("expense_ratio", 0.0)),
            category_rank_percentile=(
                100 * (1 - m["category_rank"] / m["category_size"])
                if m.get("category_rank") and m.get("category_size")
                else 50.0
            ),
            fund_xirr_pct=m.get("cagr", 0.0) * 100 if m.get("cagr") is not None else 0.0,
            category_median_xirr_pct=m.get("category_median_xirr", 0.0),
            overlap_pct_with_other_holdings=overlap_pct,
            concentration_pct_of_portfolio=concentration_pct_by_fund.get(h["fund_id"], 0.0),
            sharpe_ratio=m.get("sharpe_ratio"),
            expense_ratio_outlier_std_devs=settings.expense_ratio_outlier_std_devs,
            overlap_warning_threshold_pct=settings.overlap_warning_threshold_pct,
        )

        if verdict.confidence < settings.recommendation_confidence_floor and verdict.action != "keep":
            verdict = type(verdict)("keep", ["confidence_below_floor"], verdict.supporting_metrics, verdict.confidence)

        narration = _narrate(model, verdict.action, verdict.supporting_metrics)

        candidate = {
            "holding_id": h["holding_id"],
            "action": verdict.action,
            "switch_target_fund_id": None,
            "reason": narration["reason"],
            "supporting_metrics": verdict.supporting_metrics,
            "risk": narration["risk"],
            "expected_benefit": narration["expected_benefit"],
            "confidence": verdict.confidence,
            "generated_by_agent": AGENT_NAME,
        }
        recommendations.append(enforce_guardrails(candidate))

    return {"recommendations": recommendations}
