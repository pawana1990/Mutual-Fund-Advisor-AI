from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class PortfolioSnapshot(UUIDPrimaryKeyMixin, Base):
    """Materialized, append-only. The dashboard's hot read path reads only
    from this table — never recomputes metrics live. See ARCHITECTURE.md."""

    __tablename__ = "portfolio_snapshots"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invested_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    xirr: Mapped[float] = mapped_column(Numeric(7, 4), nullable=True)
    absolute_return_pct: Mapped[float] = mapped_column(Numeric(7, 4), nullable=True)
    asset_allocation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sector_allocation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    amc_allocation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    top_holdings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class HealthScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "health_scores"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id"), nullable=False)
    overall_score: Mapped[int] = mapped_column(nullable=False)
    diversification_score: Mapped[int] = mapped_column(nullable=False)
    risk_score: Mapped[int] = mapped_column(nullable=False)
    returns_score: Mapped[int] = mapped_column(nullable=False)
    fees_score: Mapped[int] = mapped_column(nullable=False)
    fund_quality_score: Mapped[int] = mapped_column(nullable=False)
    tax_efficiency_score: Mapped[int] = mapped_column(nullable=False)
    asset_allocation_score: Mapped[int] = mapped_column(nullable=False)
    goal_readiness_score: Mapped[int] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OverlapReport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "overlap_reports"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    overlap_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    duplicate_pairs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    amc_concentration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sector_overlap: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
