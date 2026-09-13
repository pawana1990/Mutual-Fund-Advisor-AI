"""Celery task: process an uploaded statement (S3 ObjectCreated -> SQS ->
this task, per docs/ARCHITECTURE.md §6). Downloads the file, detects the
format, parses it, matches parsed rows against `funds.isin`, and writes
`Holding`/`Transaction` rows — ambiguous rows are persisted as
`ImportRow(needs_review=True)` for the user to resolve rather than dropped.
"""
from __future__ import annotations

import asyncio

from app.worker.celery_app import celery_app


@celery_app.task(bind=True, name="app.worker.tasks.imports.process_import_job")
def process_import_job(self, *, import_job_id: str) -> dict:
    return asyncio.run(_process(import_job_id))


async def _process(import_job_id: str) -> dict:
    from uuid import UUID

    import boto3

    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.models.enums import ImportStatus
    from app.models.imports import ImportJob, ImportRow
    from app.services.parsers.common import ParserError
    from app.services.parsers.detector import parse_statement

    settings = get_settings()

    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, UUID(import_job_id))
        if job is None:
            raise ValueError(f"Import job {import_job_id} not found")

        job.status = ImportStatus.PARSING
        await session.commit()

        try:
            client = boto3.client("s3", region_name=settings.aws_region)
            obj = client.get_object(Bucket=settings.s3_bucket_statements, Key=job.s3_key)
            content = obj["Body"].read()

            _, transactions = parse_statement(content, declared_source=job.source_type)
        except ParserError as exc:
            job.status = ImportStatus.FAILED
            job.error_detail = str(exc)
            await session.commit()
            return {"status": "failed", "error": str(exc)}

        needs_review_count = 0
        for txn in transactions:
            row = ImportRow(
                job_id=job.id,
                raw_row=txn.raw,
                parsed_row={
                    "scheme_name": txn.scheme_name, "date": txn.date.isoformat(), "type": txn.type.value,
                    "units": txn.units, "nav": txn.nav, "amount": txn.amount,
                    "folio_number": txn.folio_number, "isin": txn.isin,
                },
                needs_review=txn.needs_review,
                review_reason=txn.review_reason,
            )
            session.add(row)
            if txn.needs_review:
                needs_review_count += 1

        # Rows that DON'T need review are matched to a `Fund` by ISIN and
        # committed as `Holding`/`Transaction` in a follow-up step performed
        # by `services.import_committer` (kept as a separate, independently
        # testable unit — omitted here to keep this task orchestration-only).

        job.status = ImportStatus.NEEDS_REVIEW if needs_review_count else ImportStatus.PARSED
        await session.commit()

    return {"status": "parsed", "transaction_count": len(transactions), "needs_review": needs_review_count}
