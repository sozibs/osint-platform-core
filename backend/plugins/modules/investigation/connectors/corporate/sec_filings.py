"""SEC EDGAR filings connector."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class SecFilingsConnector:
    """Searches the SEC EDGAR full-text search index for company filings."""

    def __init__(self, base_url: str = "https://data.sec.gov") -> None:
        self._base_url = base_url.rstrip("/")

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search SEC EDGAR for *company_name* and return the raw response dict.

        Queries the EDGAR full-text search for 10-K filings since 2000.
        Returns ``None`` on any HTTP or parsing error.
        """
        url = (
            "https://efts.sec.gov/LATEST/search-index"
            f"?q={quote(company_name)}"
            "&dateRange=custom&startdt=2000-01-01&forms=10-K"
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error(
                "SecFilingsConnector: HTTP error searching for '%s': %s", company_name, exc
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "SecFilingsConnector: unexpected error for '%s': %s", company_name, exc
            )
            return None
