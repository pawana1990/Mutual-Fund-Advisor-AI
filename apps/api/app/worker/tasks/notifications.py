"""Notification fan-out (email/WhatsApp/push) and the monthly tax-harvest
scan. See docs/API_DESIGN.md `Notifications` and the product spec's
notification triggers list."""
from __future__ import annotations

import asyncio

from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.notifications.send_alert")
def send_alert(*, user_id: str, alert_id: str) -> dict:
    return asyncio.run(_send_alert(user_id, alert_id))


async def _send_alert(user_id: str, alert_id: str) -> dict:
    from uuid import UUID

    from app.db.session import AsyncSessionLocal
    from app.models.alert import Alert
    from app.models.user import User
    from app.services.notifications import dispatch_alert

    async with AsyncSessionLocal() as session:
        alert = await session.get(Alert, UUID(alert_id))
        user = await session.get(User, UUID(user_id))
        if alert is None or user is None:
            return {"status": "skipped", "reason": "alert or user not found"}

        channels_sent = await dispatch_alert(alert=alert, user=user)
        alert.channels_sent = channels_sent
        await session.commit()

    return {"status": "sent", "channels": channels_sent}


@celery_app.task(name="app.worker.tasks.notifications.scan_tax_harvest_opportunities")
def scan_tax_harvest_opportunities() -> dict:
    """Monthly job: for every portfolio, run the Tax Agent's harvesting scan
    and create an `alerts` row (type=tax_harvest) when a meaningful new
    opportunity appears — a thin orchestration wrapper around
    `agents.tax_agent.run`, kept here rather than in the agent module since
    it owns DB/notification side effects the agent module intentionally
    does not (see docs/AI_AGENT_WORKFLOW.md §1 pure-function contract)."""
    return asyncio.run(_scan_all_portfolios())


async def _scan_all_portfolios() -> dict:
    from sqlalchemy import select

    from app.agents.tax_agent import run as run_tax_agent
    from app.db.session import AsyncSessionLocal
    from app.models.alert import Alert
    from app.models.enums import AlertSeverity, AlertType
    from app.models.portfolio import Portfolio
    from app.services.holding_view import load_holding_views

    alerts_created = 0
    async with AsyncSessionLocal() as session:
        portfolios = (await session.execute(select(Portfolio))).scalars().all()
        for portfolio in portfolios:
            holdings = await load_holding_views(session, portfolio.id)
            if not holdings:
                continue
            result = run_tax_agent({"holdings": holdings})
            saving = result["tax_report"].get("total_potential_tax_saving", 0.0)
            if saving > 0:
                session.add(
                    Alert(
                        user_id=portfolio.owner_user_id,
                        portfolio_id=portfolio.id,
                        type=AlertType.TAX_HARVEST,
                        severity=AlertSeverity.INFO,
                        title="Tax-harvesting opportunity available",
                        body=f"You could save an estimated ₹{saving:,.0f} in tax by harvesting "
                        "long-term gains within your unused exemption this financial year.",
                        channels_sent={},
                    )
                )
                alerts_created += 1
        await session.commit()

    return {"alerts_created": alerts_created}
