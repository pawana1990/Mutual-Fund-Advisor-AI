"""LangGraph supervisor wiring — builds the multi-agent graphs described in
docs/AI_AGENT_WORKFLOW.md.

Two graphs are exposed:

- `build_refresh_graph()` — the full pipeline run after a portfolio import or
  on a scheduled recompute: Portfolio Analysis -> {Fund Research, Overlap,
  Risk, Tax} (parallel) -> Recommendation -> Goal Planning -> Health Score.
- `build_chat_graph()` — a router node classifies the user's question intent
  and only invokes the agents needed to answer it, instead of always
  re-running the full pipeline synchronously.

Every node function is imported from its own module in `app/agents/` and is
independently unit-tested there with a `FakeChatModel` — this file only
wires topology, it contains no business logic itself.
"""
from __future__ import annotations

from functools import partial
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agents import (
    fund_research,
    goal_planning,
    health_score_aggregator,
    overlap_detection,
    portfolio_analysis,
    recommendation,
    risk_analysis,
    tax_agent,
)
from app.agents.llm import ChatModel
from app.agents.state import AdvisorState


def build_refresh_graph(*, chat_model: ChatModel | None = None):
    """`chat_model` is partial-applied into every LLM-calling node so tests
    (and the production app, which passes a real `OpenAIChatModel`) can
    inject it once at graph-build time — LangGraph invokes nodes as
    `node(state)`, so this is the seam for dependency injection."""
    graph = StateGraph(AdvisorState)

    graph.add_node("portfolio_analysis", portfolio_analysis.run)
    graph.add_node("fund_research", fund_research.run)
    graph.add_node("overlap_detection", overlap_detection.run)
    graph.add_node("risk_analysis", partial(risk_analysis.run, chat_model=chat_model))
    graph.add_node("tax_agent", tax_agent.run)
    graph.add_node("recommendation", partial(recommendation.run, chat_model=chat_model))
    graph.add_node("goal_planning", goal_planning.run)
    graph.add_node("health_score", health_score_aggregator.run)

    graph.add_edge(START, "portfolio_analysis")

    # Fan-out: these four run independently off the same portfolio_analysis
    # output and each write disjoint state keys, so LangGraph can execute
    # them concurrently (superstep semantics) before fanning back in.
    for parallel_node in ("fund_research", "overlap_detection", "risk_analysis", "tax_agent"):
        graph.add_edge("portfolio_analysis", parallel_node)
        graph.add_edge(parallel_node, "recommendation")

    graph.add_edge("recommendation", "goal_planning")
    graph.add_edge("goal_planning", "health_score")
    graph.add_edge("health_score", END)

    return graph.compile()


# --- Chat graph: intent routing so a question only invokes what it needs ---

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "risk": ["risky", "risk", "volatile", "volatility", "beta", "sharpe", "drawdown"],
    "goal": ["retire", "retirement", "crore", "goal", "fire", "reach", "afford"],
    "tax": ["tax", "ltcg", "stcg", "harvest"],
    "overlap": ["overlap", "duplicate", "similar funds"],
    "recommendation": ["exit", "sell", "switch", "should i", "increase", "reduce"],
    "compare": ["compare", "versus", " vs "],
}


def classify_chat_intent(question: str) -> str:
    lowered = question.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return intent
    return "general"


def _router_node(state: AdvisorState) -> dict:
    question = state.get("chat_question", "") or ""
    return {"chat_intent": classify_chat_intent(question)}


def _route_from_intent(state: AdvisorState) -> Literal[
    "risk_analysis", "goal_planning", "tax_agent", "overlap_detection", "recommendation", "portfolio_analysis"
]:
    intent = state.get("chat_intent", "general")
    return {
        "risk": "risk_analysis",
        "goal": "goal_planning",
        "tax": "tax_agent",
        "overlap": "overlap_detection",
        "recommendation": "recommendation",
        "compare": "portfolio_analysis",  # comparison reads from state["fund_metrics"], already fetched
        "general": "portfolio_analysis",
    }.get(intent, "portfolio_analysis")


def build_chat_graph(*, chat_model: ChatModel | None = None):
    """A lighter graph: always grounds in `portfolio_analysis`, then routes
    to exactly the specialist agent the question needs, per
    `classify_chat_intent`."""
    graph = StateGraph(AdvisorState)

    graph.add_node("router", _router_node)
    graph.add_node("portfolio_analysis", portfolio_analysis.run)
    graph.add_node("risk_analysis", partial(risk_analysis.run, chat_model=chat_model))
    graph.add_node("goal_planning", goal_planning.run)
    graph.add_node("tax_agent", tax_agent.run)
    graph.add_node("overlap_detection", overlap_detection.run)
    graph.add_node("recommendation", partial(recommendation.run, chat_model=chat_model))

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_intent,
        {
            "risk_analysis": "risk_analysis",
            "goal_planning": "goal_planning",
            "tax_agent": "tax_agent",
            "overlap_detection": "overlap_detection",
            "recommendation": "recommendation",
            "portfolio_analysis": "portfolio_analysis",
        },
    )
    for node in ("risk_analysis", "goal_planning", "tax_agent", "overlap_detection", "recommendation", "portfolio_analysis"):
        graph.add_edge(node, END)

    return graph.compile()
