"""Redis-backed sliding-window rate limiter."""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding-window rate limiter backed by Redis sorted sets.

    Algorithm
    ---------
    Each request adds a scored entry (score = current Unix timestamp in ms)
    to a per-key Redis sorted set.  Old entries outside the window are pruned
    atomically before the count is checked.  This gives a true sliding window
    without the "boundary spike" problem of the fixed-window approach.

    The implementation uses a Redis pipeline to batch all operations in a
    single round-trip:
    1. ``ZADD key score member``        – record the request
    2. ``ZREMRANGEBYSCORE key 0 cutoff`` – prune expired entries
    3. ``ZCARD key``                    – count requests in window
    4. ``PEXPIRE key window_ms``        – auto-clean the key

    Parameters
    ----------
    redis_url:
        Redis connection string, e.g. ``redis://localhost:6379/0``.
    default_limit:
        Maximum number of requests per window for a single key.
    window_seconds:
        Length of the sliding window in seconds (default 60).
    """

    def __init__(
        self,
        redis_url: str,
        default_limit: int,
        window_seconds: int = 60,
    ) -> None:
        self._redis_url = redis_url
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._client: Optional[aioredis.Redis] = None  # type: ignore[type-arg]

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def _get_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Lazily create (and cache) the async Redis client."""
        if self._client is None:
            self._client = await aioredis.from_url(
                self._redis_url,
                decode_responses=False,
                max_connections=20,
            )
        return self._client

    async def close(self) -> None:
        """Gracefully close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Core logic ─────────────────────────────────────────────────────────────

    async def is_allowed(
        self,
        key: str,
        limit: Optional[int] = None,
    ) -> Tuple[bool, int, int]:
        """
        Check whether a new request for *key* is within the rate limit.

        The request **is** recorded (counts against the limit) regardless of
        whether it is allowed.

        Parameters
        ----------
        key:
            Unique identifier for the rate-limit bucket, e.g.
            ``"rate:user:abc"`` or ``"rate:ip:1.2.3.4"``.
        limit:
            Override for the default per-window limit.

        Returns
        -------
        tuple[bool, int, int]
            ``(allowed, remaining, reset_at)`` where:
            - *allowed*  – ``True`` if the request should proceed.
            - *remaining* – Requests left in the current window (≥ 0).
            - *reset_at*  – Unix timestamp (seconds) when the window resets.
        """
        effective_limit = limit if limit is not None else self.default_limit
        window_ms = self.window_seconds * 1_000
        now_ms = int(time.time() * 1_000)
        cutoff_ms = now_ms - window_ms
        member = f"{now_ms}-{id(object())}"  # unique member per request

        try:
            client = await self._get_client()
            async with client.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {member: now_ms})
                pipe.zremrangebyscore(key, 0, cutoff_ms)
                pipe.zcard(key)
                pipe.pexpire(key, window_ms)
                results = await pipe.execute()

            request_count: int = int(results[2])
            allowed = request_count <= effective_limit
            remaining = max(0, effective_limit - request_count)
            reset_at = int((now_ms + window_ms) / 1_000)
            return allowed, remaining, reset_at

        except Exception as exc:
            # Never block a request because Redis is unavailable.
            logger.warning("Rate limiter Redis error for key %s: %s", key, exc)
            return True, effective_limit, int(time.time()) + self.window_seconds

    async def reset(self, key: str) -> None:
        """
        Remove all entries for *key*, effectively resetting its rate limit.

        Parameters
        ----------
        key:
            The rate-limit bucket key to clear.
        """
        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception as exc:
            logger.warning("Failed to reset rate limit for key %s: %s", key, exc)

    async def get_limit_info(
        self,
        key: str,
        limit: Optional[int] = None,
    ) -> Dict[str, object]:
        """
        Return rate-limit metadata for *key* **without** recording a new request.

        Parameters
        ----------
        key:
            The rate-limit bucket key to inspect.
        limit:
            Override for the default per-window limit.

        Returns
        -------
        Dict[str, object]
            Keys: ``limit``, ``remaining``, ``reset_at``, ``current_count``.
        """
        effective_limit = limit if limit is not None else self.default_limit
        window_ms = self.window_seconds * 1_000
        now_ms = int(time.time() * 1_000)
        cutoff_ms = now_ms - window_ms

        try:
            client = await self._get_client()
            async with client.pipeline(transaction=False) as pipe:
                pipe.zremrangebyscore(key, 0, cutoff_ms)
                pipe.zcard(key)
                results = await pipe.execute()

            current_count: int = int(results[1])
            remaining = max(0, effective_limit - current_count)
            reset_at = int((now_ms + window_ms) / 1_000)
            return {
                "limit": effective_limit,
                "remaining": remaining,
                "reset_at": reset_at,
                "current_count": current_count,
            }

        except Exception as exc:
            logger.warning("Failed to get limit info for key %s: %s", key, exc)
            return {
                "limit": effective_limit,
                "remaining": effective_limit,
                "reset_at": int(time.time()) + self.window_seconds,
                "current_count": 0,
            }


# Module-level singleton.
rate_limiter = RateLimiter(
    redis_url=settings.REDIS_URL,
    default_limit=settings.RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)
