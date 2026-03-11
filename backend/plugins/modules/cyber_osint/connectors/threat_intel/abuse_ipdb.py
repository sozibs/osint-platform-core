"""AbuseIPDB connector for IP abuse scoring."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"


class AbuseIpDb:
    """Queries the AbuseIPDB v2 API for IP abuse confidence scores."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    async def check(self, ip: str) -> Dict[str, Any]:
        """Return abuse data for the given IP, or an empty dict if no API key is set."""
        if not self._api_key:
            logger.debug("AbuseIpDb: no API key configured; skipping lookup for %s", ip)
            return {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    _ABUSEIPDB_URL,
                    params={"ipAddress": ip, "maxAgeInDays": 90},
                    headers={"Key": self._api_key, "Accept": "application/json"},
                )
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("AbuseIpDb HTTP %s for %s: %s", exc.response.status_code, ip, exc)
            return {}
        except httpx.HTTPError as exc:
            logger.warning("AbuseIpDb HTTP error for %s: %s", ip, exc)
            return {}
        except Exception as exc:
            logger.error("AbuseIpDb unexpected error for %s: %s", ip, exc)
            return {}

        return data.get("data", {})
