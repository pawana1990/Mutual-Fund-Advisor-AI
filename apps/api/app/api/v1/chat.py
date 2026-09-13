"""AI chat endpoint — invokes the LangGraph chat graph (intent-routed, see
docs/AI_AGENT_WORKFLOW.md §2) grounded in the portfolio's live data."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends

from app.agents.orchestrator import build_chat_graph
from app.api.v1.deps import get_owned_portfolio, get_tenant_session
from app.models.portfolio import Portfolio
from app.schemas.portfolio import ChatRequest, ChatResponse
from app.services.holding_view import load_holding_views

router = APIRouter()


@router.post("/portfolios/{portfolio_id}/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> ChatResponse:
    holdings = await load_holding_views(session, portfolio.id)
    graph = build_chat_graph()
    final_state = graph.invoke(
        {"chat_question": payload.message, "holdings": holdings, "goals": [], "fund_metrics": {}}
    )

    intent = final_state.get("chat_intent", "general")
    answer, citations = _summarize_for_chat(intent, final_state)
    return ChatResponse(answer=answer, intent=intent, citations=citations)


def _summarize_for_chat(intent: str, state: dict) -> tuple[str, dict]:
    """Turns the graph's structured output into a short natural-language
    answer + a `citations` dict the frontend can render as "based on"
    evidence chips — never free-form LLM prose detached from the numbers."""
    if intent == "risk" and state.get("risk_report", {}).get("metrics"):
        metrics = state["risk_report"]["metrics"]
        explanations = state["risk_report"].get("explanations", {})
        lines = [explanations.get(k, f"{k}: {v}") for k, v in metrics.items()]
        return " ".join(lines) or "Not enough data yet to assess risk.", metrics

    if intent == "goal" and state.get("goals"):
        goal = state["goals"][0]
        return (
            f"You need to invest ₹{goal['required_monthly_sip']:,.0f}/month to reach this goal, "
            f"with an estimated {goal['probability_of_success']:.0f}% probability of success "
            "given typical market volatility.",
            {"required_monthly_sip": goal["required_monthly_sip"], "probability_of_success": goal["probability_of_success"]},
        )

    if intent == "tax" and state.get("tax_report"):
        report = state["tax_report"]
        saving = report.get("total_potential_tax_saving", 0.0)
        return (
            f"You have ₹{saving:,.0f} in potential tax savings available via harvesting this financial year.",
            report,
        )

    if intent == "overlap" and state.get("overlap_report"):
        report = state["overlap_report"]
        return (
            f"Your portfolio's overlap is {report.get('portfolio_overlap_pct', 0)}% across your holdings.",
            report,
        )

    if intent == "recommendation" and state.get("recommendations"):
        recs = state["recommendations"]
        summary = "; ".join(f"{r['action']}: {r['reason']}" for r in recs[:3])
        return summary or "No specific recommendation at this time.", {"recommendations": recs}

    metrics = state.get("portfolio_metrics", {})
    return (
        f"Your portfolio is currently valued at ₹{metrics.get('current_value', 0):,.0f} "
        f"with an XIRR of {metrics.get('xirr', 0)}%.",
        metrics,
    )
