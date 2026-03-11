"""Certificate Transparency log search via crt.sh."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


class CertTransparency:
    """Searches certificate transparency logs using the crt.sh public API."""

    _CRT_SH_URL = "https://crt.sh/"

    async def search(self, domain: str) -> List[str]:
        """Return unique domain names found in CT logs for the given domain."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    self._CRT_SH_URL,
                    params={"q": f"%.{domain}", "output": "json"},
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                entries: List[Dict[str, Any]] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("CertTransparency HTTP error for %s: %s", domain, exc)
            return []
        except Exception as exc:
            logger.error("CertTransparency unexpected error for %s: %s", domain, exc)
            return []

        seen: set[str] = set()
        results: List[str] = []
        for entry in entries:
            name_value: str = entry.get("name_value", "")
            # name_value may contain multiple domains separated by newlines
            for name in name_value.splitlines():
                name = name.strip().lstrip("*.")
                if name and name not in seen:
                    seen.add(name)
                    results.append(name)

        return results
