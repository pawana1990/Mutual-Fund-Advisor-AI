from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HoldingSource, SipFrequency, SipStatus, TransactionType


class Portfolio(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "portfolios"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Primary")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    holdings: Mapped[list["Holding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    sips: Mapped[list["Sip"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class Holding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "fund_id", name="uq_portfolio_fund"),)

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True)
    units: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    avg_cost_nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    invested_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    current_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    source: Mapped[HoldingSource] = mapped_column(
        Enum(HoldingSource, name="holding_source_enum"), nullable=False, default=HoldingSource.MANUAL
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")
    fund = relationship("Fund")


class Transaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transactions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("holdings.id"), nullable=True, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False, index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type_enum"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    units: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    nav: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)  # signed
    folio_number: Mapped[str] = mapped_column(String(64), nullable=True)
    import_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"), nullable=True)

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")


class Sip(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sips"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    frequency: Mapped[SipFrequency] = mapped_column(
        Enum(SipFrequency, name="sip_frequency_enum"), nullable=False, default=SipFrequency.MONTHLY
    )
    day_of_month: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[SipStatus] = mapped_column(
        Enum(SipStatus, name="sip_status_enum"), nullable=False, default=SipStatus.ACTIVE
    )
    next_debit_date: Mapped[date] = mapped_column(Date, nullable=True)

    portfolio: Mapped[Portfolio] = relationship(back_populates="sips")
