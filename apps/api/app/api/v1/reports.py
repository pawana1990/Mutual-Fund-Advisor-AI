"""PDF report generation — queues a Celery job (`app.worker.tasks.reports`)
that renders the report (services/report_generator.py, ReportLab-based) and
uploads it to `S3_BUCKET_REPORTS`; polling this endpoint returns a presigned
download URL once ready. See docs/API_DESIGN.md `Reports`."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.deps import get_owned_portfolio
from app.core.config import get_settings
from app.models.portfolio import Portfolio

router = APIRouter()


class ReportRequest(BaseModel):
    include_tax_report: bool = True
    include_goal_tracking: bool = True


class ReportQueuedResponse(BaseModel):
    report_id: str
    status: str = "queued"


class ReportStatusResponse(BaseModel):
    report_id: str
    status: str  # queued | rendering | ready | failed
    download_url: str | None = None


@router.post("/portfolios/{portfolio_id}/reports", response_model=ReportQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_report(
    payload: ReportRequest,
    portfolio: Portfolio = Depends(get_owned_portfolio),
) -> ReportQueuedResponse:
    from app.worker.tasks.reports import generate_portfolio_report

    report_id = str(uuid.uuid4())
    generate_portfolio_report.delay(
        report_id=report_id,
        portfolio_id=str(portfolio.id),
        include_tax_report=payload.include_tax_report,
        include_goal_tracking=payload.include_goal_tracking,
    )
    return ReportQueuedResponse(report_id=report_id)


@router.get("/reports/{report_id}", response_model=ReportStatusResponse)
async def get_report_status(report_id: str) -> ReportStatusResponse:
    from app.worker.celery_app import celery_app

    async_result = celery_app.AsyncResult(report_id)
    if async_result.state == "PENDING":
        return ReportStatusResponse(report_id=report_id, status="queued")
    if async_result.state == "STARTED":
        return ReportStatusResponse(report_id=report_id, status="rendering")
    if async_result.state == "SUCCESS":
        settings = get_settings()
        s3_key = async_result.result.get("s3_key") if isinstance(async_result.result, dict) else None
        download_url = _presigned_url(settings.s3_bucket_reports, s3_key) if s3_key else None
        return ReportStatusResponse(report_id=report_id, status="ready", download_url=download_url)
    if async_result.state == "FAILURE":
        return ReportStatusResponse(report_id=report_id, status="failed")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown report id")


def _presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    import boto3

    client = boto3.client("s3")
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
