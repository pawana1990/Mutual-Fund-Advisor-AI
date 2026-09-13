"""Async SQLAlchemy engine/session factory + FastAPI dependency.

Sets the Postgres session variable `app.current_org_id` on every connection
checkout from the authenticated request's `Principal`, so Row-Level Security
policies (defined in the Alembic migrations) enforce tenant isolation even
if a repository query forgets an explicit `organization_id` filter.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def set_tenant_context(session: AsyncSession, organization_id: str) -> None:
    """Must be called before any query in a request handler that has a
    resolved `Principal`, so RLS policies scope correctly."""
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, true)"),
        {"org_id": organization_id},
    )
