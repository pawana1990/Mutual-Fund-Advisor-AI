"""Scheduled jobs: nightly NAV refresh (AMFI bulk NAV file) and weekly AMC
news scan feeding the News Intelligence Agent. See docs/ARCHITECTURE.md §5
(EventBridge Scheduler in prod triggers these via ECS RunTask/Lambda)."""
from __future__ import annotations

import asyncio

from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.market_data.refresh_all_fund_navs")
def refresh_all_fund_navs() -> dict:
    return asyncio.run(_refresh_navs())


async def _refresh_navs() -> dict:
    """Downloads AMFI's daily bulk NAV file (`AMFI_NAV_URL`), a pipe-delimited
    text file keyed by scheme code, and upserts `funds.current_nav` +
    appends to `fund_nav_history`. The AMFI feed format is stable and
    well-documented; parsing logic below reflects its actual layout:
    `Scheme Code;ISIN Div Payout;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date`.
    """
    import httpx

    from app.core.config import get_settings
    from app.core.logging import get_logger
    from app.db.session import AsyncSessionLocal
    from app.services.market_data import parse_amfi_nav_file, upsert_fund_navs

    settings = get_settings()
    logger = get_logger(__name__)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(settings.amfi_nav_url)
        response.raise_for_status()
        rows = parse_amfi_nav_file(response.text)

    async with AsyncSessionLocal() as session:
        updated = await upsert_fund_navs(session, rows)
        await session.commit()

    logger.info("nav_refresh_complete", updated_count=updated)
    return {"updated_count": updated}


@celery_app.task(name="app.worker.tasks.market_data.scan_amc_news")
def scan_amc_news() -> dict:
    """Placeholder orchestration point for the News Intelligence Agent's
    scheduled run (fetch from a news provider, classify via
    `agents.news_intelligence.classify_news_item`, persist `alerts` for
    matches against the watchlist). Left as a documented integration point
    since it depends on a specific news-provider contract to be chosen —
    see docs/AI_AGENT_WORKFLOW.md agent contract table."""
    return {"status": "not_yet_wired_to_a_news_provider"}
