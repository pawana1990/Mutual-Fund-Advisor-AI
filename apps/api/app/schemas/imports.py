from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.models.enums import HoldingSource, ImportStatus


class UploadUrlRequest(BaseModel):
    source_type: HoldingSource
    filename: str


class UploadUrlResponse(BaseModel):
    import_job_id: UUID
    upload_url: str
    s3_key: str
    expires_in_seconds: int = 900


class ImportRowOut(BaseModel):
    id: UUID
    needs_review: bool
    review_reason: str | None
    parsed_row: dict | None


class ImportJobOut(BaseModel):
    id: UUID
    source_type: HoldingSource
    status: ImportStatus
    error_detail: str | None
    rows_needing_review: list[ImportRowOut] = []


class ResolveRowRequest(BaseModel):
    corrected_row: dict
