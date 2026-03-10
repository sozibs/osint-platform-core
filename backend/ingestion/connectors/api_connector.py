"""Async HTTP API connector for fetching data from external APIs."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0  # seconds


class APIConnectorError(Exception):
    """Raised when an API request fails after all retries."""


class APIConnector:
    """Production-ready async HTTP API connector with retry, rate-limiting, and pagination."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        rate_limit_per_second: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.rate_limit_per_second = rate_limit_per_second
        self._min_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

        merged_headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            merged_headers.update(headers)
        if api_key:
            merged_headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=merged_headers,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Enforce rate limiting between requests."""
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait = self._min_interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = time.monotonic()

    async def _do_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute a single HTTP request (no retry logic)."""
        await self._throttle()
        kwargs: Dict[str, Any] = {}
        if params:
            kwargs["params"] = params
        if body is not None:
            kwargs["json"] = body

        return await self._client.request(method.upper(), url, **kwargs)

    # ── Public interface ──────────────────────────────────────────────────────

    async def fetch(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch data from an API endpoint with exponential backoff retry.

        Returns a dict containing ``data`` (parsed JSON), ``status_code``,
        ``headers``, and ``request_url``.
        """
        url = endpoint if endpoint.startswith("http") else f"/{endpoint.lstrip('/')}"
        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._do_request(method, url, params=params, body=body)

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                    logger.warning(
                        "Rate limited by %s (429). Waiting %.1fs (attempt %d/%d).",
                        endpoint,
                        retry_after,
                        attempt,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code in _DEFAULT_RETRY_STATUSES:
                    backoff = _BASE_BACKOFF ** attempt
                    logger.warning(
                        "HTTP %d from %s. Retrying in %.1fs (attempt %d/%d).",
                        response.status_code,
                        endpoint,
                        backoff,
                        attempt,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                    continue

                response.raise_for_status()

                try:
                    data = response.json()
                except Exception:
                    data = {"raw": response.text}

                return {
                    "data": data,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "request_url": str(response.url),
                }

            except httpx.TimeoutException as exc:
                last_exc = exc
                backoff = _BASE_BACKOFF ** attempt
                logger.warning(
                    "Timeout on %s (attempt %d/%d). Retrying in %.1fs.",
                    endpoint,
                    attempt,
                    _MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.error("HTTP error %d from %s: %s", exc.response.status_code, endpoint, exc)
                break

            except httpx.RequestError as exc:
                last_exc = exc
                backoff = _BASE_BACKOFF ** attempt
                logger.warning(
                    "Request error on %s (attempt %d/%d): %s. Retrying in %.1fs.",
                    endpoint,
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise APIConnectorError(
            f"Failed to fetch {endpoint} after {_MAX_RETRIES} attempts: {last_exc}"
        ) from last_exc

    async def fetch_paginated(
        self,
        endpoint: str,
        page_param: str = "page",
        page_size_param: str = "per_page",
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch all pages from a page-number-based paginated API.

        Stops when a page returns an empty list or fewer items than ``page_size``.
        The API response is expected to return a list directly or a dict with a
        ``results`` / ``data`` / ``items`` key containing the list.
        """
        all_results: List[Dict[str, Any]] = []
        page = 1

        while True:
            params: Dict[str, Any] = {page_param: page, page_size_param: page_size}
            try:
                result = await self.fetch(endpoint, params=params)
            except APIConnectorError:
                logger.error("Stopping pagination for %s at page %d due to error.", endpoint, page)
                break

            raw = result["data"]
            if isinstance(raw, list):
                items = raw
            elif isinstance(raw, dict):
                for key in ("results", "data", "items", "records", "entries"):
                    if key in raw and isinstance(raw[key], list):
                        items = raw[key]
                        break
                else:
                    items = []
            else:
                items = []

            if not items:
                break

            all_results.extend(items)
            logger.debug("Fetched page %d with %d items from %s.", page, len(items), endpoint)

            if len(items) < page_size:
                break

            page += 1

        return all_results

    async def stream_results(
        self,
        endpoint: str,
        cursor_param: str = "cursor",
    ) -> AsyncIterator[Dict[str, Any]]:
        """Async generator for cursor-based pagination.

        Yields individual records. Stops when the API returns no next cursor.
        """
        cursor: Optional[str] = None

        while True:
            params: Dict[str, Any] = {}
            if cursor:
                params[cursor_param] = cursor

            try:
                result = await self.fetch(endpoint, params=params)
            except APIConnectorError:
                logger.error("Stopping cursor pagination for %s.", endpoint)
                return

            raw = result["data"]
            if isinstance(raw, dict):
                items = []
                for key in ("results", "data", "items", "records", "entries"):
                    if key in raw and isinstance(raw[key], list):
                        items = raw[key]
                        break

                next_cursor = (
                    raw.get("next_cursor")
                    or raw.get("cursor")
                    or (raw.get("meta") or {}).get("next_cursor")
                )
            else:
                items = raw if isinstance(raw, list) else []
                next_cursor = None

            for item in items:
                yield item

            if not next_cursor or not items:
                break

            cursor = str(next_cursor)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
        logger.debug("APIConnector HTTP client closed.")

    async def __aenter__(self) -> "APIConnector":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
