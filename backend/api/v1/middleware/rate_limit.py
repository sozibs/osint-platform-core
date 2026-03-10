"""
Rate-limiting middleware.

Uses the Redis-backed sliding-window ``RateLimiter`` to enforce per-user
(or per-IP for unauthenticated requests) request limits.

Headers set on every response:
- ``X-RateLimit-Limit``     – Requests allowed per window.
- ``X-RateLimit-Remaining`` – Requests remaining in the current window.
- ``X-RateLimit-Reset``     – Unix timestamp when the window resets.

Returns **HTTP 429** with a ``Retry-After`` header when the limit is exceeded.
"""
from __future__ import annotations

import logging

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from security.rate_limiting.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting.
_EXEMPT_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})

# Authenticated users get a higher per-minute allowance than anonymous callers.
_AUTHENTICATED_LIMIT = 120
_ANONYMOUS_LIMIT = 30


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate-limiting ASGI middleware.

    Bucket keys:
    - Authenticated: ``rate:user:<user_id>``
    - Anonymous:     ``rate:ip:<client_ip>``
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Determine the rate-limit bucket and per-request limit.
        user_id: str | None = getattr(request.state, "user_id", None)
        if user_id:
            bucket_key = f"rate:user:{user_id}"
            limit = _AUTHENTICATED_LIMIT
        else:
            client_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else "unknown")
            )
            bucket_key = f"rate:ip:{client_ip}"
            limit = _ANONYMOUS_LIMIT

        allowed, remaining, reset_at = await rate_limiter.is_allowed(
            bucket_key, limit=limit
        )

        if not allowed:
            retry_after = max(1, reset_at - int(__import__("time").time()))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please retry after the window resets.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        response = await call_next(request)

        # Attach rate-limit headers to every successful response.
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response
