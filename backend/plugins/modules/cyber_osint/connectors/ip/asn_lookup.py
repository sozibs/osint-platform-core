"""ASN lookup connector using ipinfo.io (free tier)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class AsnLookup:
    """Retrieves ASN information for an IP using ipinfo.io."""

    _BASE_URL = "https://ipinfo.io"

    async def lookup(self, ip: str) -> Dict[str, Any]:
        """Return org and asn fields extracted from ipinfo.io for the given IP."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._BASE_URL}/{ip}/json",
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("AsnLookup HTTP error for %s: %s", ip, exc)
            return {"ip": ip}
        except Exception as exc:
            logger.error("AsnLookup unexpected error for %s: %s", ip, exc)
            return {"ip": ip}

        org: str = data.get("org", "")
        # org field from ipinfo is formatted as "AS12345 Some ISP Name"
        parts = org.split(" ", 1)
        asn = parts[0] if parts else None
        asn_name = parts[1] if len(parts) > 1 else None

        return {
            "ip": ip,
            "org": org,
            "asn": asn,
            "asn_name": asn_name,
        }
