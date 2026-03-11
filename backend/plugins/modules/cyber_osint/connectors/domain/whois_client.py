"""WHOIS client connector."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class WhoisClient:
    """Fetches WHOIS information for a domain."""

    async def lookup(self, domain: str) -> Dict[str, Any]:
        """Return WHOIS data for the given domain if the whois library is available."""
        loop = asyncio.get_event_loop()
        try:
            import whois  # type: ignore[import-untyped]

            result = await loop.run_in_executor(None, whois.whois, domain)
            data: Dict[str, Any] = dict(result) if result else {}

            # Normalize dates that may come as lists
            for date_key in ("creation_date", "expiration_date", "updated_date"):
                value = data.get(date_key)
                if isinstance(value, list):
                    data[date_key] = value[0] if value else None

            # Normalize nameservers that may come as lists of strings
            ns = data.get("name_servers")
            if isinstance(ns, list):
                data["nameservers"] = [str(n).lower() for n in ns]
            elif isinstance(ns, str):
                data["nameservers"] = [ns.lower()]
            else:
                data["nameservers"] = []

            data.setdefault("domain", domain)
            return data

        except ImportError:
            logger.debug("whois library not installed; returning basic dict for %s", domain)
            return {"domain": domain}
        except Exception as exc:
            logger.warning("WhoisClient lookup failed for %s: %s", domain, exc)
            return {"domain": domain}
