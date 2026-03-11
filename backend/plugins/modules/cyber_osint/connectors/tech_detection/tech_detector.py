"""Technology detection connector using HTTP response analysis."""

from __future__ import annotations

import ipaddress
import logging
from typing import Dict, List
from urllib.parse import urlparse

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

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Return True only if the URL uses http/https and does not target a private/loopback address."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Block localhost by name
    if hostname.lower() in ("localhost", "::1"):
        return False

    try:
        addr = ipaddress.ip_address(hostname)
        for network in _PRIVATE_NETWORKS:
            if addr in network:
                return False
    except ValueError:
        # Not an IP literal — treat as a domain name, which is acceptable
        pass

    return True


class TechDetector:
    """Detects web technologies from HTTP response headers and body content."""

    async def detect(self, url: str) -> List[str]:
        """Return a list of technology names detected on the given URL."""
        if not _is_safe_url(url):
            logger.warning("TechDetector blocked potentially unsafe URL: %s", url)
            return []

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
