"""DKIM record checker."""

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


class DkimChecker:
    """Checks for the presence of a DKIM DNS record for a given selector."""

    async def check(self, domain: str, selector: str = "default") -> Dict[str, Any]:
        """Return DKIM record details for the given domain and selector."""
        dkim_domain = f"{selector}._domainkey.{domain}"
        loop = asyncio.get_event_loop()
        txt_records: List[str] = await loop.run_in_executor(None, _get_txt_records, dkim_domain)

        dkim_record: Optional[str] = None
        for record in txt_records:
            if "v=DKIM1" in record or "k=rsa" in record or "p=" in record:
                dkim_record = record
                break

        return {
            "domain": domain,
            "selector": selector,
            "has_dkim": dkim_record is not None,
            "dkim_record": dkim_record,
        }
