"""Google Fact Check Tools API connector."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from ...models.factcheck import FactCheck

logger = logging.getLogger(__name__)


class GoogleFactCheck:
    """Client for the Google Fact Check Tools API."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://factchecktools.googleapis.com/v1alpha1",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str) -> List[FactCheck]:
        """Search Google Fact Check Tools for claims matching *query*.

        Returns a list of :class:`FactCheck` objects, or an empty list when no
        API key is configured.
        """
        if not self._api_key:
            logger.warning(
                "GOOGLE_FACTCHECK_API_KEY is not set; returning empty results."
            )
            return []

        params = urlencode({"query": query, "key": self._api_key})
        url = f"{self._base_url}/claims:search?{params}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _parse_response(self, data: Dict[str, Any]) -> List[FactCheck]:
        factchecks: List[FactCheck] = []
        for item in data.get("claims", []):
            claim_text: str = item.get("text", "")
            for review in item.get("claimReview", []):
                publisher: Dict[str, Any] = review.get("publisher", {})
                fact_checker = publisher.get("name", "Unknown")
                fact_check_url: Optional[str] = review.get("url")
                rating_value: Optional[str] = (
                    review.get("textualRating")
                    or review.get("reviewRating", {}).get("alternateName")
                )
                verdict = rating_value or "unrated"
                factchecks.append(
                    FactCheck(
                        claim_text=claim_text,
                        verdict=verdict,
                        rating=rating_value,
                        fact_checker=fact_checker,
                        fact_check_url=fact_check_url,
                        explanation=review.get("title"),
                    )
                )
        return factchecks
