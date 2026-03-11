"""DNS analyzer: performs basic DNS lookups for a domain."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _resolve_a(domain: str) -> List[str]:
    try:
        infos = socket.getaddrinfo(domain, None, socket.AF_INET)
        return list({info[4][0] for info in infos})
    except socket.gaierror:
        return []


def _resolve_aaaa(domain: str) -> List[str]:
    try:
        infos = socket.getaddrinfo(domain, None, socket.AF_INET6)
        return list({info[4][0] for info in infos})
    except socket.gaierror:
        return []


def _blocking_dns(domain: str) -> Dict[str, Any]:
    return {
        "A": _resolve_a(domain),
        "AAAA": _resolve_aaaa(domain),
    }


class DnsAnalyzer:
    async def analyze(self, domain: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            records = await loop.run_in_executor(None, _blocking_dns, domain)
        except Exception as exc:
            logger.error("DNS analysis failed for '%s': %s", domain, exc)
            records = {}

        return records
