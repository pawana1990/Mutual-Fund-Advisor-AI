from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RollingWindow:
    ONE_YEAR = "1y"
    THREE_YEAR = "3y"
    FIVE_YEAR = "5y"


class Fund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Shared reference data — NOT tenant-scoped. One row per scheme."""

    __tablename__ = "funds"

    isin: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amc: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(120), nullable=True)
    benchmark: Mapped[str] = mapped_column(String(120), nullable=True)
    fund_manager: Mapped[str] = mapped_column(String(255), nullable=True)
    expense_ratio: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    aum_cr: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)
    exit_load_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    inception_date: Mapped[date] = mapped_column(Date, nullable=True)
    current_nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    current_nav_date: Mapped[date] = mapped_column(Date, nullable=True)

    nav_history: Mapped[list["FundNavHistory"]] = relationship(back_populates="fund")
    risk_metrics: Mapped[list["FundRiskMetrics"]] = relationship(back_populates="fund")


class FundNavHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fund_nav_history"
    __table_args__ = (UniqueConstraint("fund_id", "nav_date", name="uq_fund_nav_date"),)

    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)

    fund: Mapped[Fund] = relationship(back_populates="nav_history")


class FundRiskMetrics(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recomputed nightly per fund per rolling window."""

    __tablename__ = "fund_risk_metrics"
    __table_args__ = (UniqueConstraint("fund_id", "window", name="uq_fund_risk_window"),)

    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(4), nullable=False)  # 1y | 3y | 5y
    cagr: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    beta: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    alpha: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    sharpe_ratio: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    sortino_ratio: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    std_deviation: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Numeric(9, 4), nullable=True)
    category_rank: Mapped[int] = mapped_column(nullable=True)
    category_size: Mapped[int] = mapped_column(nullable=True)

    fund: Mapped[Fund] = relationship(back_populates="risk_metrics")
