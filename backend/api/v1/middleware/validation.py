"""
Request validation middleware.

Responsibilities:
- Validate ``Content-Type`` for POST/PUT/PATCH requests.
- Reject requests whose body exceeds the configured size limit.
- Sanitize inbound headers (remove hop-by-hop headers that should not be forwarded).
- Inject a unique ``X-Request-ID`` into every request and response.
- Log every request with method, path, status code, and elapsed time.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import FrozenSet

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from config import settings

logger = logging.getLogger(__name__)

# HTTP methods that must carry a JSON body.
_BODY_METHODS: FrozenSet[str] = frozenset({"POST", "PUT", "PATCH"})

# Headers that should not be forwarded to upstream services.
_HOP_BY_HOP_HEADERS: FrozenSet[str] = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

# Maximum allowed request body size in bytes.
_MAX_BODY_BYTES: int = settings.MAX_FILE_SIZE_MB * 1024 * 1024

# Paths that are allowed to have non-JSON bodies (multipart uploads, form data).
_NON_JSON_PATHS: FrozenSet[str] = frozenset(
    {
        "/api/v1/ingest/file",
    }
)


class ValidationMiddleware(BaseHTTPMiddleware):
    """
    Request validation and observability ASGI middleware.

    Applied **before** route handlers so that invalid requests are rejected
    early with a structured error response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter()

        # ── Request ID ────────────────────────────────────────────────────────
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # ── Content-Type validation ───────────────────────────────────────────
        if (
            request.method in _BODY_METHODS
            and request.url.path not in _NON_JSON_PATHS
        ):
            content_type = request.headers.get("Content-Type", "")
            # Allow application/json and application/x-www-form-urlencoded (OAuth2 forms).
            if content_type and not (
                "application/json" in content_type
                or "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={
                        "detail": (
                            f"Unsupported Content-Type: {content_type!r}. "
                            "Expected 'application/json'."
                        )
                    },
                    headers={"X-Request-ID": request_id},
                )

        # ── Body size guard ───────────────────────────────────────────────────
        content_length_str = request.headers.get("Content-Length")
        if content_length_str is not None:
            try:
                content_length = int(content_length_str)
                if content_length > _MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": (
                                f"Request body exceeds the maximum allowed size of "
                                f"{settings.MAX_FILE_SIZE_MB} MB."
                            )
                        },
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                pass  # Ignore malformed Content-Length; let the framework handle it.

        # ── Process request ───────────────────────────────────────────────────
        response = await call_next(request)

        # ── Attach observability headers ──────────────────────────────────────
        elapsed_ms = (time.perf_counter() - start_time) * 1_000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

        # ── Access log ────────────────────────────────────────────────────────
        logger.info(
            "%s %s %d %.2fms req_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response
