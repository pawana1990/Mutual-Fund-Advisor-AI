"""FastAPI application entrypoint. See docs/ARCHITECTURE.md for the
system-level picture this app sits inside."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", environment=settings.environment)
    yield
    logger.info("shutdown")


app = FastAPI(
    title="AI Wealth Advisor API",
    description="Evidence-first, multi-agent mutual-fund portfolio intelligence.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_local else None,
    redoc_url="/redoc" if settings.is_local else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_local else [],  # tightened via env-driven allow-list in non-local envs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attaches a request id (propagated to logs + response header) and
    timing — the minimal cut of what CloudWatch/X-Ray correlate on in
    production (see docs/MONITORING.md)."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """OWASP-recommended security headers (see docs/SECURITY.md A05)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if not settings.is_local:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """RFC 7807 problem+json error shape — see docs/API_DESIGN.md `Conventions`."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "Error",
            "status": exc.status_code,
            "instance": str(request.url.path),
        },
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "about:blank",
            "title": "Validation Error",
            "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "instance": str(request.url.path),
            "errors": exc.errors(),
        },
        media_type="application/problem+json",
    )


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    """Liveness probe — no dependency checks, just "is the process up"."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict:
    """Readiness probe — verifies the DB is reachable before ALB routes
    traffic to this task (see docs/DEPLOYMENT_GUIDE.md)."""
    from sqlalchemy import text

    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # pragma: no cover - exercised only when DB is actually down
        return JSONResponse(status_code=503, content={"status": "not_ready", "detail": str(exc)})


app.include_router(api_router, prefix=settings.api_v1_prefix)
