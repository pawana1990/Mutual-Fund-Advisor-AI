from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RecommendationAction, RecommendationStatus


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every field below `reason` is required (non-nullable). The API and
    the AI guardrail (`app/agents/guardrails.py`) both refuse to persist a
    recommendation missing evidence — see docs/AI_AGENT_WORKFLOW.md §4."""

    __tablename__ = "recommendations"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("holdings.id"), nullable=True)
    action: Mapped[RecommendationAction] = mapped_column(
        Enum(RecommendationAction, name="recommendation_action_enum"), nullable=False
    )
    switch_target_fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    expected_benefit: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status_enum"),
        nullable=False,
        default=RecommendationStatus.OPEN,
    )
    generated_by_agent: Mapped[str] = mapped_column(String(120), nullable=False)
