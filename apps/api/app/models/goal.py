from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GoalType


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    type: Mapped[GoalType] = mapped_column(Enum(GoalType, name="goal_type_enum"), nullable=False)
    target_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_progress_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    required_monthly_sip: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    assumed_return_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=11.0)
    probability_of_success: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)


class GoalProjection(UUIDPrimaryKeyMixin, Base):
    """One row per percentile band of a Monte Carlo projection run."""

    __tablename__ = "goal_projections"

    goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True)
    percentile: Mapped[int] = mapped_column(nullable=False)  # 10, 25, 50, 75, 90
    projected_value_by_year: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
