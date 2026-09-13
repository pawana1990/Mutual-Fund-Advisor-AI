"""Current-user preference endpoints — see docs/API_DESIGN.md `Notifications`."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_tenant_session
from app.core.security import Principal, get_current_principal
from app.models.user import User

router = APIRouter()


class NotificationPrefsUpdate(BaseModel):
    email: bool | None = None
    whatsapp: bool | None = None
    push: bool | None = None
    phone_number: str | None = None
    device_token: str | None = None


class NotificationPrefsOut(BaseModel):
    email: bool
    whatsapp: bool
    push: bool


@router.patch("/me/notification-prefs", response_model=NotificationPrefsOut)
async def update_notification_prefs(
    payload: NotificationPrefsUpdate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> NotificationPrefsOut:
    user = await session.get(User, principal.user_id)
    prefs = dict(user.notification_prefs or {})
    for field in ("email", "whatsapp", "push", "phone_number", "device_token"):
        value = getattr(payload, field)
        if value is not None:
            prefs[field] = value
    user.notification_prefs = prefs
    await session.commit()
    return NotificationPrefsOut(
        email=prefs.get("email", True), whatsapp=prefs.get("whatsapp", False), push=prefs.get("push", True)
    )
