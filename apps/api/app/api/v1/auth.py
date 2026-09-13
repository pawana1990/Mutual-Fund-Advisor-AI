"""Signup/login are handled by Cognito Hosted UI / Amplify directly from the
frontend (see docs/API_DESIGN.md `Auth`) — this router only exposes what
must be server-side: the authenticated profile lookup and the post-signup
webhook that provisions our `users` row."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_tenant_session
from app.core.security import Principal, get_current_principal
from app.models.user import User

router = APIRouter()


class MeResponse(BaseModel):
    user_id: str
    organization_id: str
    email: str
    role: str
    risk_profile: str | None = None


@router.get("/me", response_model=MeResponse)
async def read_current_user(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> MeResponse:
    result = await session.execute(select(User).where(User.id == principal.user_id))
    user = result.scalar_one_or_none()
    return MeResponse(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        email=principal.email,
        role=principal.role.value,
        risk_profile=user.risk_profile.value if user else None,
    )
