"""HaveIBeenPwned breach checker."""

from __future__ import annotations

import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

_HIBP_API_BASE = "https://haveibeenpwned.com/api/v3"


class BreachChecker:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    async def check(self, email: str) -> List[str]:
        if not self._api_key:
            logger.warning(
                "HaveIBeenPwned API key not configured; skipping breach check for '%s'",
                email,
            )
            return []

        url = f"{_HIBP_API_BASE}/breachedaccount/{email}"
        headers = {
            "hibp-api-key": self._api_key,
            "user-agent": "osint-platform/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params={"truncateResponse": "false"})

            if response.status_code == 404:
                return []

            response.raise_for_status()
            breaches = response.json()
            return [b.get("Name", "") for b in breaches if b.get("Name")]
        except httpx.HTTPStatusError as exc:
            logger.error("HIBP HTTP error for '%s': %s", email, exc)
        except httpx.RequestError as exc:
            logger.error("HIBP request error for '%s': %s", email, exc)

        return []
