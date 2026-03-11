"""ClaimBuster connector for the IDIR ClaimBuster fact-checking API."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class ClaimBuster:
    """Client for the ClaimBuster claim-scoring API."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://idir.uta.edu/claimbuster/api/v2",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def check_claim(self, text: str) -> Dict[str, Any]:
        """Score *text* for claim-worthiness via the ClaimBuster API.

        Returns the raw API response dict, or a default payload when no API key
        is configured.
        """
        if not self._api_key:
            logger.warning(
                "CLAIMBUSTER_API_KEY is not set; returning default zero-score response."
            )
            return {"score": 0.0, "sentences": []}

        url = f"{self._base_url}/score/text/"
        headers = {"x-api-key": self._api_key}
        payload = {"input_text": text}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
