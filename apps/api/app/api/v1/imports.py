"""Statement import endpoints. Upload goes directly to S3 via a presigned
URL (never through the API tier — see docs/SECURITY.md `File upload
safety`); this router only issues the URL and reports job status."""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_portfolio, get_tenant_session
from app.core.config import get_settings
from app.models.enums import ImportStatus
from app.models.imports import ImportJob, ImportRow
from app.models.portfolio import Portfolio
from app.schemas.imports import (
    ImportJobOut,
    ImportRowOut,
    ResolveRowRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)

router = APIRouter()


@router.post("/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    payload: UploadUrlRequest,
    portfolio: Portfolio = Depends(get_owned_portfolio),
    session: AsyncSession = Depends(get_tenant_session),
) -> UploadUrlResponse:
    import boto3

    settings = get_settings()
    job_id = uuid.uuid4()
    s3_key = f"statements/{portfolio.organization_id}/{portfolio.id}/{job_id}_{payload.filename}"

    job = ImportJob(
        id=job_id, portfolio_id=portfolio.id, source_type=payload.source_type,
        s3_key=s3_key, status=ImportStatus.PENDING,
    )
    session.add(job)
    await session.commit()

    client = boto3.client("s3", region_name=settings.aws_region)
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket_statements, "Key": s3_key, "ContentType": "application/octet-stream"},
        ExpiresIn=900,
    )
    return UploadUrlResponse(import_job_id=job_id, upload_url=upload_url, s3_key=s3_key)


@router.post("/{job_id}/notify-uploaded", status_code=status.HTTP_202_ACCEPTED)
async def notify_uploaded(job_id: UUID, session: AsyncSession = Depends(get_tenant_session)) -> dict:
    """In production, S3 `ObjectCreated` -> SQS triggers
    `process_import_job` automatically (see docs/ARCHITECTURE.md §6). This
    endpoint exists for local dev / environments without SQS wired, so the
    frontend can explicitly signal "the presigned PUT finished" and queue
    the same task directly."""
    from app.worker.tasks.imports import process_import_job

    job = await session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    process_import_job.delay(import_job_id=str(job_id))
    return {"status": "queued"}


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_import_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_tenant_session),
) -> ImportJobOut:
    job = await session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")

    rows_result = await session.execute(
        select(ImportRow).where(ImportRow.job_id == job.id, ImportRow.needs_review.is_(True))
    )
    return ImportJobOut(
        id=job.id, source_type=job.source_type, status=job.status, error_detail=job.error_detail,
        rows_needing_review=[
            ImportRowOut(id=r.id, needs_review=r.needs_review, review_reason=r.review_reason, parsed_row=r.parsed_row)
            for r in rows_result.scalars().all()
        ],
    )


@router.post("/{job_id}/rows/{row_id}/resolve", response_model=ImportRowOut)
async def resolve_import_row(
    job_id: UUID,
    row_id: UUID,
    payload: ResolveRowRequest,
    session: AsyncSession = Depends(get_tenant_session),
) -> ImportRowOut:
    row = await session.get(ImportRow, row_id)
    if row is None or row.job_id != job_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import row not found")

    row.parsed_row = payload.corrected_row
    row.needs_review = False
    row.review_reason = None
    await session.commit()
    return ImportRowOut(id=row.id, needs_review=row.needs_review, review_reason=row.review_reason, parsed_row=row.parsed_row)
