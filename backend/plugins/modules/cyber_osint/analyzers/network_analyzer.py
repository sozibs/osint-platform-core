"""Network analyzer — builds a comprehensive network profile for an IP address."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from ..connectors.ip.asn_lookup import AsnLookup
from ..connectors.ip.ip_lookup import IpLookup

logger = logging.getLogger(__name__)


class NetworkAnalyzer:
    """Combines IP lookup and ASN information into a comprehensive network profile."""

    def __init__(self) -> None:
        self._ip_lookup = IpLookup()
        self._asn_lookup = AsnLookup()

    async def analyze(self, ip: str) -> Dict[str, Any]:
        """Return a merged network profile dict for the given IP."""
        ip_result, asn_result = await asyncio.gather(
            self._ip_lookup.lookup(ip),
            self._asn_lookup.lookup(ip),
            return_exceptions=True,
        )

        profile: Dict[str, Any] = {"ip": ip}

        if isinstance(ip_result, Exception):
            logger.warning("NetworkAnalyzer IP lookup failed for %s: %s", ip, ip_result)
        else:
            profile.update(ip_result.model_dump())

        if isinstance(asn_result, Exception):
            logger.warning("NetworkAnalyzer ASN lookup failed for %s: %s", ip, asn_result)
        else:
            # ASN lookup may refine the asn/org fields
            for key in ("org", "asn", "asn_name"):
                if asn_result.get(key):
                    profile[key] = asn_result[key]

        return profile
