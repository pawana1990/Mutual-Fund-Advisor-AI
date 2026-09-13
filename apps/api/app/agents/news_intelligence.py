"""News Intelligence Agent — runs on a scheduled trigger (Celery beat), NOT
per-request (see docs/AI_AGENT_WORKFLOW.md §2). Classifies incoming AMC/fund
news, SEBI circulars, and market events for relevance to a watchlist of
funds, and emits `alerts`-shaped signals for the notification pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.agents.llm import ChatModel, get_chat_model


class NewsCategory(StrEnum):
    FUND_MANAGER_CHANGE = "manager_change"
    EXPENSE_RATIO_CHANGE = "expense_ratio_change"
    CATEGORY_CHANGE = "category_change"
    SEBI_CIRCULAR = "sebi_circular"
    AMC_NEWS = "amc_news"
    MARKET_EVENT = "market_event"
    IRRELEVANT = "irrelevant"


@dataclass(frozen=True, slots=True)
class NewsSignal:
    fund_id: str | None
    amc: str | None
    category: NewsCategory
    headline: str
    summary: str
    severity: str  # info | warning | critical
    source_url: str | None


_KEYWORD_CATEGORY_MAP: list[tuple[str, NewsCategory]] = [
    ("fund manager", NewsCategory.FUND_MANAGER_CHANGE),
    ("appointed as fund manager", NewsCategory.FUND_MANAGER_CHANGE),
    ("expense ratio", NewsCategory.EXPENSE_RATIO_CHANGE),
    ("total expense ratio", NewsCategory.EXPENSE_RATIO_CHANGE),
    ("scheme category", NewsCategory.CATEGORY_CHANGE),
    ("fundamental attribute", NewsCategory.CATEGORY_CHANGE),
    ("sebi circular", NewsCategory.SEBI_CIRCULAR),
    ("securities and exchange board of india", NewsCategory.SEBI_CIRCULAR),
]


def classify_news_item(headline: str, body: str) -> NewsCategory:
    """Deterministic keyword pre-filter before any LLM call — cheap items
    (SEBI circular language is highly formulaic) never need to hit the LLM
    at all; ambiguous items fall through to `summarize_and_classify`."""
    text = f"{headline} {body}".lower()
    for keyword, category in _KEYWORD_CATEGORY_MAP:
        if keyword in text:
            return category
    return NewsCategory.IRRELEVANT


def watchlist_relevance(fund_names: list[str], body: str) -> str | None:
    """Simple substring match against the user's watchlist — cheap, no LLM,
    used to decide whether an item is even worth further processing."""
    lowered = body.lower()
    for name in fund_names:
        if name.lower() in lowered:
            return name
    return None


def summarize_news_item(
    headline: str,
    body: str,
    *,
    chat_model: ChatModel | None = None,
) -> str:
    model = chat_model or get_chat_model()
    return model.complete(
        system=(
            "Summarize this mutual-fund/market news item in 1-2 sentences of plain English for a retail "
            "investor, focused on what action-relevant fact it contains (a change, a risk, an event) — "
            "never speculate beyond what the text says."
        ),
        user=f"Headline: {headline}\n\nBody:\n{body}",
    )
