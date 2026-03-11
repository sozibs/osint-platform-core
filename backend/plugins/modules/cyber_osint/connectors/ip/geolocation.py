"""Geolocation connector using ipinfo.io (free tier)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class Geolocation:
    """Retrieves geolocation data for an IP using ipinfo.io."""

    _BASE_URL = "https://ipinfo.io"

    async def locate(self, ip: str) -> Dict[str, Any]:
        """Return country, city, region, and loc (lat,lon) for the given IP."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._BASE_URL}/{ip}/json",
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Geolocation HTTP error for %s: %s", ip, exc)
            return {"ip": ip}
        except Exception as exc:
            logger.error("Geolocation unexpected error for %s: %s", ip, exc)
            return {"ip": ip}

        return {
            "ip": data.get("ip", ip),
            "country": data.get("country"),
            "city": data.get("city"),
            "region": data.get("region"),
            "loc": data.get("loc"),
            "org": data.get("org"),
            "hostname": data.get("hostname"),
            "timezone": data.get("timezone"),
        }
