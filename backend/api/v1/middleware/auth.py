"""
Authentication middleware.

Extracts the caller's identity from either a Bearer JWT or an X-API-Key
header and attaches the resolved ``User`` ORM object to ``request.state.user``.

Public paths listed in ``PUBLIC_PATHS`` bypass authentication entirely.
"""
from __future__ import annotations

import logging
from typing import FrozenSet

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from security.auth.api_key_manager import api_key_manager
from security.auth.jwt_handler import jwt_handler

logger = logging.getLogger(__name__)

# Paths that do not require authentication.
PUBLIC_PATHS: FrozenSet[str] = frozenset(
    {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }
)


def _is_public(path: str) -> bool:
    """Return ``True`` if *path* does not require authentication."""
    if path in PUBLIC_PATHS:
        return True
    # Allow access to static assets bundled with Swagger/ReDoc.
    if path.startswith(("/docs/", "/redoc/", "/openapi")):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that validates authentication credentials on every request.

    For protected routes it:
    1. Checks for a ``Bearer`` JWT in the ``Authorization`` header.
    2. Falls back to the ``X-API-Key`` header.
    3. Returns **HTTP 401** if neither is present or valid.

    On success it stores the resolved user (a lightweight dict to avoid
    SQLAlchemy session issues across middleware/route boundary) in
    ``request.state.user_id`` and ``request.state.user_role``.

    Full ORM-model resolution is delegated to the route-level
    ``get_current_user`` dependency so that a proper async session is used.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Always set a default so downstream code can rely on these attrs.
        request.state.user_id = None
        request.state.user_role = None
        request.state.auth_method = None

        if _is_public(request.url.path):
            return await call_next(request)

        # ── 1. Bearer JWT ─────────────────────────────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            payload = jwt_handler.verify_token(token)
            if payload is None or payload.get("type") != "access":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or expired access token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            request.state.user_id = payload.get("sub")
            request.state.user_role = payload.get("role")
            request.state.auth_method = "jwt"
            return await call_next(request)

        # ── 2. X-API-Key ──────────────────────────────────────────────────────
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            # We can't easily use async SQLAlchemy here without a session, so
            # we store a sentinel and let the route dependency do full validation.
            # Still, we verify basic key format to reject obviously bad keys fast.
            if api_key_header.startswith("osint_") and len(api_key_header) > 10:
                request.state.auth_method = "api_key"
                request.state.raw_api_key = api_key_header
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid API key format"},
            )

        # ── 3. No credentials ─────────────────────────────────────────────────
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication credentials were not provided"},
            headers={"WWW-Authenticate": "Bearer"},
        )
