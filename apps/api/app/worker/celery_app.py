"""Celery application — the async task runner for imports, report
generation, and scheduled jobs (nightly NAV refresh, weekly news scan,
monthly tax-harvest scan). See docs/ARCHITECTURE.md §4-5."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_wealth_advisor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.worker.tasks.imports",
        "app.worker.tasks.reports",
        "app.worker.tasks.market_data",
        "app.worker.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=15 * 60,
)

celery_app.conf.beat_schedule = {
    "nightly-nav-refresh": {
        "task": "app.worker.tasks.market_data.refresh_all_fund_navs",
        "schedule": crontab(hour=21, minute=30),  # ~9:30pm IST, after market close data settles
    },
    "weekly-news-scan": {
        "task": "app.worker.tasks.market_data.scan_amc_news",
        "schedule": crontab(hour=6, minute=0, day_of_week="monday"),
    },
    "monthly-tax-harvest-scan": {
        "task": "app.worker.tasks.notifications.scan_tax_harvest_opportunities",
        "schedule": crontab(hour=7, minute=0, day_of_month="1"),
    },
}
