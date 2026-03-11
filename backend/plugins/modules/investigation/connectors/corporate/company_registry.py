"""OpenCorporates company registry connector."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from ...models.org_profile import OrgProfile

logger = logging.getLogger(__name__)


class CompanyRegistry:
    """Looks up company information via the OpenCorporates API."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    async def lookup(
        self, company_name: str, jurisdiction: str = "us"
    ) -> Optional[OrgProfile]:
        """Return an :class:`OrgProfile` for *company_name* in *jurisdiction*.

        Uses the OpenCorporates API when an API key is configured; otherwise
        returns a minimal profile containing only the company name.
        """
        if not self._api_key:
            logger.warning(
                "CompanyRegistry: OPENCORPORATES_API_KEY not configured — "
                "returning basic profile for '%s'",
                company_name,
            )
            return OrgProfile(
                name=company_name,
                jurisdiction=jurisdiction,
                sources=["basic"],
            )

        url = (
            "https://api.opencorporates.com/v0.4/companies/search"
            f"?q={quote(company_name)}&jurisdiction_code={jurisdiction}"
            f"&api_token={self._api_key}"
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error(
                "CompanyRegistry: HTTP error looking up '%s': %s", company_name, exc
            )
            return OrgProfile(name=company_name, jurisdiction=jurisdiction, sources=["basic"])

        companies: list[Dict[str, Any]] = (
            data.get("results", {}).get("companies", [])
        )
        if not companies:
            return OrgProfile(name=company_name, jurisdiction=jurisdiction, sources=["opencorporates"])

        first: Dict[str, Any] = companies[0].get("company", {})
        return OrgProfile(
            name=first.get("name", company_name),
            registration_number=first.get("company_number"),
            jurisdiction=first.get("jurisdiction_code", jurisdiction),
            industry=first.get("industry_codes", [None])[0]
            if first.get("industry_codes")
            else None,
            website=first.get("home_member", {}).get("url"),
            founded_date=first.get("incorporation_date"),
            status=first.get("current_status"),
            addresses=[first.get("registered_address_in_full", "")]
            if first.get("registered_address_in_full")
            else [],
            confidence_score=0.8,
            sources=["opencorporates"],
        )
