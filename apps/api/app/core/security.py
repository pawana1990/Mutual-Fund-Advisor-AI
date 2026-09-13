"""AuthN/AuthZ: Cognito JWT verification, `Principal` extraction, RBAC guard.

Every authenticated request resolves to a `Principal`, which every
repository/service call downstream is required to take — see
`apps/api/app/db/repositories/` and `docs/SECURITY.md` for the tenant
isolation model this enforces.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError

from app.core.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=True)

_jwks_cache: dict[str, object] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


class Role(StrEnum):
    OWNER = "owner"
    ADVISOR = "advisor"
    CLIENT_VIEWER = "client_viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller. Every downstream query is scoped by this."""

    user_id: str
    organization_id: str
    role: Role
    email: str


async def _get_jwks() -> dict:
    settings = get_settings()
    now = time.time()
    if _jwks_cache["keys"] is not None and now - float(_jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]  # type: ignore[return-value]

    url = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        jwks = resp.json()

    _jwks_cache["keys"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks


async def decode_token(token: str) -> dict:
    """Verify signature (against Cognito JWKS) + standard claims."""
    settings = get_settings()

    if settings.is_local and not settings.cognito_user_pool_id:
        # Local/dev convenience: accept unsigned dev tokens shaped like the
        # real claims so the API is exercisable without a live Cognito pool.
        # NEVER enabled outside `environment == "local"`.
        try:
            return jwt.get_unverified_claims(token)
        except JOSEError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc

    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")

        claims = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.cognito_app_client_id,
            options={"verify_aud": bool(settings.cognito_app_client_id)},
        )
        return claims
    except JOSEError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> Principal:
    claims = await decode_token(credentials.credentials)
    try:
        return Principal(
            user_id=claims["sub"],
            organization_id=claims["custom:organization_id"],
            role=Role(claims.get("custom:role", Role.CLIENT_VIEWER.value)),
            email=claims.get("email", ""),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token claims") from exc


def require_role(*allowed: Role):
    """FastAPI dependency factory: `Depends(require_role(Role.ADVISOR, Role.ADMIN))`."""

    async def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{principal.role}' is not permitted to perform this action",
            )
        return principal

    return _dependency
