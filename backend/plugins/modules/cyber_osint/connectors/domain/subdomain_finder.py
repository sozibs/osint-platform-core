"""Subdomain finder connector using DNS brute-forcing."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import List

logger = logging.getLogger(__name__)

_COMMON_SUBDOMAINS: List[str] = [
    "www", "mail", "ftp", "admin", "api", "dev", "staging", "test",
    "blog", "shop", "portal", "app", "secure", "vpn", "remote",
]


class SubdomainFinder:
    """Discovers subdomains by attempting DNS resolution of common prefixes."""

    async def _resolve_subdomain(self, subdomain: str) -> str | None:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, socket.getaddrinfo, subdomain, None)
            return subdomain
        except socket.gaierror:
            return None
        except Exception as exc:
            logger.debug("SubdomainFinder resolution error for %s: %s", subdomain, exc)
            return None

    async def find(self, domain: str) -> List[str]:
        """Return a list of discovered subdomains for the given domain."""
        candidates = [f"{sub}.{domain}" for sub in _COMMON_SUBDOMAINS]
        results = await asyncio.gather(
            *[self._resolve_subdomain(candidate) for candidate in candidates]
        )
        return [r for r in results if r is not None]
