"""VirusTotal connector for IP and domain threat intelligence."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ...models.threat_indicator import ThreatIndicator

logger = logging.getLogger(__name__)

_VT_BASE = "https://www.virustotal.com/api/v3"


class VirusTotalClient:
    """Queries the VirusTotal API v3 for threat intelligence."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {"x-apikey": self._api_key, "Accept": "application/json"}

    def _severity_from_stats(self, malicious: int, total: int) -> str:
        if total == 0:
            return "unknown"
        ratio = malicious / total
        if ratio >= 0.5:
            return "high"
        if ratio >= 0.2:
            return "medium"
        if malicious > 0:
            return "low"
        return "clean"

    async def _query(self, endpoint: str, indicator: str, indicator_type: str) -> ThreatIndicator:
        if not self._api_key:
            logger.debug("VirusTotalClient: no API key configured; returning low-confidence result")
            return ThreatIndicator(
                indicator=indicator,
                indicator_type=indicator_type,
                sources=["virustotal"],
                confidence=0.0,
                severity="unknown",
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(endpoint, headers=self._headers())
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("VirusTotalClient HTTP %s for %s: %s", exc.response.status_code, indicator, exc)
            return ThreatIndicator(indicator=indicator, indicator_type=indicator_type, sources=["virustotal"])
        except httpx.HTTPError as exc:
            logger.warning("VirusTotalClient HTTP error for %s: %s", indicator, exc)
            return ThreatIndicator(indicator=indicator, indicator_type=indicator_type, sources=["virustotal"])
        except Exception as exc:
            logger.error("VirusTotalClient unexpected error for %s: %s", indicator, exc)
            return ThreatIndicator(indicator=indicator, indicator_type=indicator_type, sources=["virustotal"])

        attrs: Dict[str, Any] = data.get("data", {}).get("attributes", {})
        stats: Dict[str, int] = attrs.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        total = sum(stats.values())
        confidence = malicious / total if total else 0.0
        severity = self._severity_from_stats(malicious, total)
        tags = attrs.get("tags", [])

        return ThreatIndicator(
            indicator=indicator,
            indicator_type=indicator_type,
            severity=severity,
            confidence=confidence,
            sources=["virustotal"],
            tags=tags,
        )

    async def check_ip(self, ip: str) -> ThreatIndicator:
        """Check a given IP address against VirusTotal."""
        return await self._query(f"{_VT_BASE}/ip_addresses/{ip}", ip, "ip")

    async def check_domain(self, domain: str) -> ThreatIndicator:
        """Check a given domain against VirusTotal."""
        return await self._query(f"{_VT_BASE}/domains/{domain}", domain, "domain")
