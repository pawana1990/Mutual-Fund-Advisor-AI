"""Fund Research Agent — surfaces NAV, expense ratio, manager, AUM,
benchmark, category ranking and rolling returns for one or more funds.

The numeric fields are read straight from `fund_metrics`/reference data
(populated by the nightly AMFI/provider sync job — see
docs/ARCHITECTURE.md §4), never computed or guessed by the LLM. The LLM's
only job here is to summarize a fund's latest factsheet commentary (via RAG
over `kb_chunks`, see docs/AI_AGENT_WORKFLOW.md §5) when a chat question
asks something qualitative (e.g. "what's this fund's investment style?").
"""
from __future__ import annotations

from app.agents.llm import ChatModel, get_chat_model
from app.agents.state import AdvisorState

AGENT_NAME = "fund_research_agent_v1"


def run(state: AdvisorState) -> dict:
    """Populates/refreshes `state["fund_metrics"]` entries used by every
    downstream agent. In production this reads from the `funds` /
    `fund_risk_metrics` tables (already refreshed nightly); this function
    is intentionally a passthrough here — the real I/O lives in the
    repository layer (`app/db/repositories/fund_repository.py`), keeping
    this module DB-free and unit-testable."""
    return {"fund_metrics": state.get("fund_metrics", {})}


def summarize_fund_commentary(
    fund_name: str,
    factsheet_excerpts: list[str],
    *,
    chat_model: ChatModel | None = None,
) -> str:
    """RAG-style summarization: `factsheet_excerpts` are the top-k pgvector
    matches for the fund's latest factsheet/commentary, retrieved and
    filtered by fund_id BEFORE this call (see docs/AI_AGENT_WORKFLOW.md §5)
    — this function never does its own retrieval, keeping it pure/testable.
    """
    if not factsheet_excerpts:
        return f"No recent factsheet commentary is available for {fund_name} yet."

    model = chat_model or get_chat_model()
    context = "\n---\n".join(factsheet_excerpts)
    return model.complete(
        system=(
            "You summarize mutual fund factsheet commentary for a retail investor in 3-4 plain-English "
            "sentences. Only use information present in the provided excerpts — never invent facts."
        ),
        user=f"Fund: {fund_name}\n\nExcerpts:\n{context}",
    )
