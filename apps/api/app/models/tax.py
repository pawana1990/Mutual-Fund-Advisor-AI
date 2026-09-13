from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaxRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_records"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    financial_year: Mapped[str] = mapped_column(String(9), nullable=False)  # e.g. "2025-26"
    ltcg: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    stcg: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    ltcg_tax: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    stcg_tax: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    harvesting_opportunities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
