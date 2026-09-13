"""Celery task: render + upload a portfolio PDF report. Runs the same
LangGraph refresh pipeline used by `POST /portfolios/{id}/recompute` to get
current metrics, then hands them to `services/report_generator.py`."""
from __future__ import annotations

import asyncio
from datetime import date

from app.worker.celery_app import celery_app


@celery_app.task(bind=True, name="app.worker.tasks.reports.generate_portfolio_report")
def generate_portfolio_report(
    self, *, report_id: str, portfolio_id: str, include_tax_report: bool, include_goal_tracking: bool
) -> dict:
    return asyncio.run(_generate(report_id, portfolio_id, include_tax_report, include_goal_tracking))


async def _generate(report_id: str, portfolio_id: str, include_tax_report: bool, include_goal_tracking: bool) -> dict:
    import boto3
    from uuid import UUID

    from app.agents.orchestrator import build_refresh_graph
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.models.portfolio import Portfolio
    from app.services.holding_view import load_holding_views
    from app.services.report_generator import ReportData, render_portfolio_report

    settings = get_settings()

    async with AsyncSessionLocal() as session:
        portfolio = await session.get(Portfolio, UUID(portfolio_id))
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings = await load_holding_views(session, portfolio.id)
        graph = build_refresh_graph()
        state = graph.invoke({"portfolio_id": portfolio_id, "holdings": holdings, "goals": [], "fund_metrics": {}})

    pm = state.get("portfolio_metrics", {})
    data = ReportData(
        portfolio_name=portfolio.name,
        generated_on=date.today(),
        invested_value=pm.get("invested_value", 0.0),
        current_value=pm.get("current_value", 0.0),
        xirr=pm.get("xirr", 0.0),
        absolute_return_pct=pm.get("absolute_return_pct", 0.0),
        health_score=state.get("health_score", {}),
        risk_metrics=state.get("risk_report", {}).get("metrics", {}),
        recommendations=state.get("recommendations", []),
        tax_summary=state.get("tax_report") if include_tax_report else None,
        goals=state.get("goals", []) if include_goal_tracking else [],
    )
    pdf_bytes = render_portfolio_report(data)

    s3_key = f"reports/{portfolio_id}/{report_id}.pdf"
    client = boto3.client("s3", region_name=settings.aws_region)
    client.put_object(
        Bucket=settings.s3_bucket_reports, Key=s3_key, Body=pdf_bytes, ContentType="application/pdf"
    )
    return {"s3_key": s3_key}
