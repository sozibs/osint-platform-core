"""Reverse image search connector."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ReverseImageSearch:
    """Connector for reverse image search services.

    TinEye and Google Reverse Image Search both require API keys or browser
    automation that goes beyond a simple HTTP request.  This connector returns
    a structured response directing the analyst to perform manual verification.
    """

    async def search(self, image_url: str) -> Dict[str, Any]:
        """Return instructions for manually verifying *image_url*.

        Automated reverse image search requires:
        - **TinEye**: sign up for an API key at https://services.tineye.com/
        - **Google**: use the Vision API (https://cloud.google.com/vision)

        Returns a dict with the image URL, status, and available services.
        """
        logger.info(
            "Reverse image search requested for %s; returning manual verification guidance.",
            image_url,
        )
        return {
            "image_url": image_url,
            "status": "manual_verification_required",
            "services": ["TinEye", "Google Reverse Image Search"],
        }
