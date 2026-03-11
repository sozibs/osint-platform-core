"""SPF record checker."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_txt_records(domain: str) -> List[str]:
    """Retrieve TXT records for a domain via getaddrinfo workaround using dns.resolver if available."""
    try:
        import dns.resolver  # type: ignore[import-untyped]

        answers = dns.resolver.resolve(domain, "TXT")
        return [b"".join(rdata.strings).decode("utf-8", errors="replace") for rdata in answers]
    except ImportError:
        pass
    except Exception:
        pass
    return []


class SpfChecker:
    """Checks for the presence and policy of an SPF DNS record."""

    async def check(self, domain: str) -> Dict[str, Any]:
        """Return SPF record details for the given domain."""
        loop = asyncio.get_event_loop()
        txt_records: List[str] = await loop.run_in_executor(None, _get_txt_records, domain)

        spf_record: Optional[str] = None
        for record in txt_records:
            if record.startswith("v=spf1"):
                spf_record = record
                break

        policy: Optional[str] = None
        if spf_record:
            for token in spf_record.split():
                if token in ("~all", "-all", "+all", "?all"):
                    policy = token
                    break

        return {
            "domain": domain,
            "has_spf": spf_record is not None,
            "spf_record": spf_record,
            "policy": policy,
        }
