"""Assembles every domain router under the `/api/v1` prefix — see
docs/API_DESIGN.md for the full endpoint catalogue."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    auth,
    chat,
    funds,
    goals,
    imports,
    portfolios,
    recommendations,
    reports,
    tax,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(portfolios.router, prefix="/portfolios", tags=["portfolios"])
api_router.include_router(funds.router, prefix="/funds", tags=["funds"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(goals.router, tags=["goals"])
api_router.include_router(tax.router, tags=["tax"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
