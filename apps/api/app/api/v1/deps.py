"""Shared FastAPI dependencies for the v1 API: a tenant-scoped DB session
and a helper to load+authorize a portfolio for the current principal."""
from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Role, get_current_principal
from app.db.session import AsyncSessionLocal, set_tenant_context
from app.models.portfolio import Portfolio


async def get_tenant_session(
    principal: Principal = Depends(get_current_principal),
) -> AsyncIterator[AsyncSession]:
    """A DB session with `app.current_org_id` set for RLS AND the
    `Principal` available to every repository call for explicit
    application-layer filtering — belt and suspenders, see
    docs/SECURITY.md."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, principal.organization_id)
        yield session


async def get_owned_portfolio(
    portfolio_id: UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_tenant_session),
) -> Portfolio:
    stmt = select(Portfolio).where(
        Portfolio.id == portfolio_id,
        Portfolio.organization_id == principal.organization_id,
    )
    if principal.role == Role.CLIENT_VIEWER:
        stmt = stmt.where(Portfolio.owner_user_id == principal.user_id)

    result = await session.execute(stmt)
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portfolio not found")
    return portfolio
