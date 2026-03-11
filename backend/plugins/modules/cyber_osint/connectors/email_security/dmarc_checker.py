"""DMARC record checker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_txt_records(domain: str) -> List[str]:
    try:
        import dns.resolver  # type: ignore[import-untyped]

        answers = dns.resolver.resolve(domain, "TXT")
        return [b"".join(rdata.strings).decode("utf-8", errors="replace") for rdata in answers]
    except ImportError:
        pass
    except Exception:
        pass
    return []


class DmarcChecker:
    """Checks for the presence and policy of a DMARC DNS record."""

    async def check(self, domain: str) -> Dict[str, Any]:
        """Return DMARC record details for the given domain."""
        dmarc_domain = f"_dmarc.{domain}"
        loop = asyncio.get_event_loop()
        txt_records: List[str] = await loop.run_in_executor(None, _get_txt_records, dmarc_domain)

        dmarc_record: Optional[str] = None
        for record in txt_records:
            if record.startswith("v=DMARC1"):
                dmarc_record = record
                break

        policy: Optional[str] = None
        if dmarc_record:
            for token in dmarc_record.split(";"):
                token = token.strip()
                if token.startswith("p="):
                    policy = token[2:].strip()
                    break

        return {
            "domain": domain,
            "has_dmarc": dmarc_record is not None,
            "dmarc_record": dmarc_record,
            "policy": policy,
        }
