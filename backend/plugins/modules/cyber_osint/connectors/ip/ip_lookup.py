"""IP lookup connector using ip-api.com (free, no API key required)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ...models.ip_record import IpRecord

logger = logging.getLogger(__name__)


class IpLookup:
    """Looks up IP address information using the ip-api.com free API."""

    _BASE_URL = "http://ip-api.com/json"

    async def lookup(self, ip: str) -> IpRecord:
        """Fetch geolocation and network info for the given IP address."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._BASE_URL}/{ip}")
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("IpLookup HTTP error for %s: %s", ip, exc)
            return IpRecord(ip=ip)
        except Exception as exc:
            logger.error("IpLookup unexpected error for %s: %s", ip, exc)
            return IpRecord(ip=ip)

        if data.get("status") != "success":
            logger.warning("IpLookup non-success status for %s: %s", ip, data.get("message"))
            return IpRecord(ip=ip)

        # Parse lat/lon from the "lat"/"lon" fields
        lat = data.get("lat")
        lon = data.get("lon")

        return IpRecord(
            ip=ip,
            ip_version=6 if ":" in ip else 4,
            country=data.get("country"),
            city=data.get("city"),
            region=data.get("regionName"),
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            isp=data.get("isp"),
            org=data.get("org"),
            asn=data.get("as"),
        )
