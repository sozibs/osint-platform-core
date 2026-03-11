"""Metadata extractor: fetches Open Graph, meta tags, and HTTP headers from a URL."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_OG_TAGS = ["og:title", "og:description", "og:image", "og:url"]
_META_TAGS = ["description", "keywords", "author"]
_HTTP_HEADERS = ["last-modified", "content-type"]

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_url(url: str) -> None:
    """Raise ValueError if *url* is not a safe http/https URL."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )
    if not parsed.netloc:
        raise ValueError("URL must include a hostname.")


class MetadataExtractor:
    """Extracts metadata from web pages for content verification."""

    async def extract(self, url: str) -> Dict[str, Any]:
        """Fetch *url* and return extracted Open Graph, meta, and HTTP metadata."""
        result: Dict[str, Any] = {
            "url": url,
            "open_graph": {},
            "meta": {},
            "http_headers": {},
            "error": None,
        }

        try:
            _validate_url(url)
        except ValueError as exc:
            result["error"] = str(exc)
            return result

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "OSINT-Platform-MetadataExtractor/1.0"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            html = response.text

            # Extract HTTP headers of interest
            for header in _HTTP_HEADERS:
                value = response.headers.get(header)
                if value:
                    result["http_headers"][header] = value

            # Extract Open Graph tags
            for tag in _OG_TAGS:
                value = self._extract_meta(html, property_attr=tag)
                if value:
                    result["open_graph"][tag] = value

            # Extract standard meta tags
            for tag in _META_TAGS:
                value = self._extract_meta(html, name_attr=tag)
                if value:
                    result["meta"][tag] = value

        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP error fetching %s: %s", url, exc)
            result["error"] = f"HTTP {exc.response.status_code}"
        except httpx.RequestError as exc:
            logger.warning("Request error fetching %s: %s", url, exc)
            result["error"] = str(exc)

        return result

    @staticmethod
    def _extract_meta(
        html: str,
        *,
        property_attr: Optional[str] = None,
        name_attr: Optional[str] = None,
    ) -> Optional[str]:
        """Extract a ``content`` attribute from a ``<meta>`` tag."""
        if property_attr:
            pattern = (
                r'<meta[^>]+property=["\']'
                + re.escape(property_attr)
                + r'["\'][^>]+content=["\']([^"\']*)["\']'
                r'|<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']'
                + re.escape(property_attr)
                + r'["\']'
            )
        elif name_attr:
            pattern = (
                r'<meta[^>]+name=["\']'
                + re.escape(name_attr)
                + r'["\'][^>]+content=["\']([^"\']*)["\']'
                r'|<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']'
                + re.escape(name_attr)
                + r'["\']'
            )
        else:
            return None

        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return next((g for g in match.groups() if g is not None), None)
        return None
