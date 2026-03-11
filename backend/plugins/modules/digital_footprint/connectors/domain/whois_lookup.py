"""WHOIS lookup connector for domain intelligence."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, List, Optional

from ...models.domain_record import DomainRecord

logger = logging.getLogger(__name__)


def _parse_whois_date(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
    return None


def _safe_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _blocking_whois(domain: str) -> DomainRecord:
    try:
        import whois  # type: ignore[import]

        w = whois.whois(domain)
        return DomainRecord(
            domain=domain,
            registrar=str(w.registrar) if w.registrar else None,
            creation_date=_parse_whois_date(w.creation_date),
            expiration_date=_parse_whois_date(w.expiration_date),
            nameservers=_safe_str_list(w.name_servers),
            is_active=True,
        )
    except ImportError:
        logger.warning("'whois' library not installed; returning basic DomainRecord for '%s'", domain)
    except Exception as exc:
        logger.error("WHOIS lookup failed for '%s': %s", domain, exc)

    return DomainRecord(domain=domain)


class WhoisLookup:
    async def lookup(self, domain: str) -> DomainRecord:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _blocking_whois, domain)
