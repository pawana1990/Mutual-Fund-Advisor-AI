from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HoldingSource, ImportStatus


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False, index=True)
    source_type: Mapped[HoldingSource] = mapped_column(Enum(HoldingSource, name="import_source_enum"), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status_enum"), nullable=False, default=ImportStatus.PENDING
    )
    error_detail: Mapped[str] = mapped_column(Text, nullable=True)

    rows: Mapped[list["ImportRow"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class ImportRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_rows"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"), nullable=False, index=True)
    raw_row: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parsed_row: Mapped[dict] = mapped_column(JSONB, nullable=True)
    needs_review: Mapped[bool] = mapped_column(nullable=False, default=False)
    review_reason: Mapped[str] = mapped_column(Text, nullable=True)

    job: Mapped[ImportJob] = relationship(back_populates="rows")
