"""Infrastructure mapper — combines IP and DNS data into a unified profile."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from ..connectors.domain.dns_resolver import DnsResolver
from ..connectors.ip.ip_lookup import IpLookup

logger = logging.getLogger(__name__)


class InfrastructureMapper:
    """Maps the network infrastructure for a domain or IP address."""

    def __init__(self) -> None:
        self._ip_lookup = IpLookup()
        self._dns_resolver = DnsResolver()

    async def map(self, domain_or_ip: str) -> Dict[str, Any]:
        """Run IP lookup and DNS resolution in parallel and merge results."""
        ip_result, dns_result = await asyncio.gather(
            self._ip_lookup.lookup(domain_or_ip),
            self._dns_resolver.resolve(domain_or_ip),
            return_exceptions=True,
        )

        infrastructure: Dict[str, Any] = {"target": domain_or_ip}

        if isinstance(ip_result, Exception):
            logger.warning("InfrastructureMapper IP lookup failed for %s: %s", domain_or_ip, ip_result)
        else:
            infrastructure["ip_info"] = ip_result.model_dump()

        if isinstance(dns_result, Exception):
            logger.warning("InfrastructureMapper DNS resolution failed for %s: %s", domain_or_ip, dns_result)
        else:
            infrastructure["dns_info"] = dns_result

        return infrastructure
