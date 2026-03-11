"""Business records connector using SEC EDGAR."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote

import httpx

from ...models.public_record import PublicRecord

logger = logging.getLogger(__name__)

_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


class BusinessRecordsConnector:
    """Retrieves basic business registration data from SEC EDGAR."""

    async def search(self, company_name: str) -> List[PublicRecord]:
        """Search SEC EDGAR for *company_name* and return matching records."""
        url = (
            f"{_EDGAR_SEARCH_URL}"
            f"?q={quote(company_name)}"
            "&dateRange=custom&startdt=2000-01-01&forms=10-K"
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            logger.error(
                "BusinessRecordsConnector: HTTP error for '%s': %s", company_name, exc
            )
            return []

        hits: List[Dict[str, Any]] = data.get("hits", {}).get("hits", [])
        records: List[PublicRecord] = []

        for hit in hits:
            source: Dict[str, Any] = hit.get("_source", {})
            records.append(
                PublicRecord(
                    record_type="sec_filing",
                    title=source.get("display_names", [company_name])[0],
                    description=source.get("file_date"),
                    date=source.get("file_date"),
                    jurisdiction="us",
                    source_url=(
                        f"https://www.sec.gov/cgi-bin/browse-edgar"
                        f"?action=getcompany&company={quote(company_name)}&type=10-K"
                    ),
                    raw_data=source,
                )
            )

        return records
