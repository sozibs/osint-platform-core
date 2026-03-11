"""DNS resolver connector using asyncio executor and socket."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class DnsResolver:
    """Resolves DNS records for a domain using the system resolver."""

    async def resolve(self, domain: str) -> Dict[str, Any]:
        """Return A records and reverse DNS hostname for the given domain."""
        loop = asyncio.get_event_loop()
        a_records: List[str] = []
        hostname: str | None = None

        try:
            addr_infos = await loop.run_in_executor(
                None, socket.getaddrinfo, domain, None
            )
            seen: set[str] = set()
            for info in addr_infos:
                addr = info[4][0]
                if addr not in seen:
                    seen.add(addr)
                    a_records.append(addr)
        except socket.gaierror as exc:
            logger.warning("DnsResolver getaddrinfo failed for %s: %s", domain, exc)
        except Exception as exc:
            logger.error("DnsResolver unexpected error for %s: %s", domain, exc)

        if a_records:
            try:
                hostname, _, _ = await loop.run_in_executor(
                    None, socket.gethostbyaddr, a_records[0]
                )
            except socket.herror:
                pass
            except Exception as exc:
                logger.debug("DnsResolver reverse DNS failed for %s: %s", a_records[0], exc)

        return {
            "domain": domain,
            "a_records": a_records,
            "hostname": hostname,
        }
