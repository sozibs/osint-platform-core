"""Technology detection connector using HTTP response analysis."""

from __future__ import annotations

import logging
from typing import Dict, List

import httpx

logger = logging.getLogger(__name__)

_TECH_PATTERNS: Dict[str, str] = {
    "WordPress": "wp-content",
    "Nginx": "nginx",
    "Apache": "apache",
    "React": "react",
    "Vue.js": "vue",
    "jQuery": "jquery",
    "Bootstrap": "bootstrap",
    "Cloudflare": "cloudflare",
    "Google Analytics": "gtag(",
    "Drupal": "drupal",
}


class TechDetector:
    """Detects web technologies from HTTP response headers and body content."""

    async def detect(self, url: str) -> List[str]:
        """Return a list of technology names detected on the given URL."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("TechDetector HTTP error for %s: %s", url, exc)
            return []
        except Exception as exc:
            logger.error("TechDetector unexpected error for %s: %s", url, exc)
            return []

        # Combine headers and body into a single searchable string (lowercase)
        headers_str = " ".join(
            f"{k}: {v}" for k, v in response.headers.items()
        ).lower()
        body_str = response.text.lower()
        combined = headers_str + " " + body_str

        detected: List[str] = []
        for tech, pattern in _TECH_PATTERNS.items():
            if pattern.lower() in combined:
                detected.append(tech)

        return detected
