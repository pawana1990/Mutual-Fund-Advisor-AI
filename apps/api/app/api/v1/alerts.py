"""Alert/notification-preference endpoints — see docs/API_DESIGN.md `Notifications`."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_tenant_session
from app.core.security import Principal, get_current_principal
from app.models.alert import Alert

router = APIRouter()


class AlertOut(BaseModel):
    id: UUID
    type: str
    severity: str
    title: str
    body: str
    read_at: datetime | None


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    unread_only: bool = Query(default=False),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[AlertOut]:
    stmt = select(Alert).where(Alert.user_id == principal.user_id)
    if unread_only:
        stmt = stmt.where(Alert.read_at.is_(None))
    result = await session.execute(stmt.order_by(Alert.created_at.desc()))
    return [
        AlertOut(id=a.id, type=a.type.value, severity=a.severity.value, title=a.title, body=a.body, read_at=a.read_at)
        for a in result.scalars().all()
    ]


@router.patch("/{alert_id}/read", response_model=AlertOut)
async def mark_alert_read(
    alert_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> AlertOut:
    alert = await session.get(Alert, alert_id)
    if alert is None or str(alert.user_id) != principal.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.read_at = datetime.now(timezone.utc)
    await session.commit()
    return AlertOut(id=alert.id, type=alert.type.value, severity=alert.severity.value, title=alert.title, body=alert.body, read_at=alert.read_at)

