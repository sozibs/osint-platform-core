"""Email address validator with format checking and MX record verification."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
from typing import List

from ...models.email_record import EmailRecord

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "tempmail.com",
        "throwaway.email",
        "sharklasers.com",
        "guerrillamailblock.com",
        "grr.la",
        "guerrillamail.info",
        "spam4.me",
        "yopmail.com",
        "trashmail.com",
        "dispostable.com",
        "fakeinbox.com",
        "mailnull.com",
        "spamgourmet.com",
    }
)


def _resolve_host(domain: str) -> List[str]:
    """Return resolved IP addresses for the domain as a basic reachability check.

    A proper MX lookup requires a DNS resolver library (e.g. dnspython).  Until
    that dependency is available we fall back to address resolution, which at
    minimum confirms the domain exists in DNS.
    """
    try:
        results = socket.getaddrinfo(domain, None)
        return list({r[4][0] for r in results if r[4]})
    except socket.gaierror:
        return []


class EmailValidator:
    async def validate(self, email: str) -> EmailRecord:
        email = email.strip().lower()
        is_valid = bool(_EMAIL_RE.match(email))
        domain = email.split("@")[-1] if "@" in email else ""
        is_disposable = domain in _DISPOSABLE_DOMAINS

        mx_records: List[str] = []
        if is_valid and domain:
            try:
                loop = asyncio.get_event_loop()
                mx_records = await loop.run_in_executor(None, _resolve_host, domain)
            except Exception as exc:
                logger.debug("MX lookup failed for domain '%s': %s", domain, exc)

        reputation_score = self._compute_reputation(is_valid, is_disposable, bool(mx_records))

        return EmailRecord(
            email=email,
            is_valid=is_valid,
            is_disposable=is_disposable,
            domain=domain,
            mx_records=mx_records,
            reputation_score=reputation_score,
        )

    @staticmethod
    def _compute_reputation(is_valid: bool, is_disposable: bool, has_mx: bool) -> float:
        score = 0.0
        if is_valid:
            score += 0.5
        if has_mx:
            score += 0.3
        if is_disposable:
            score -= 0.4
        return round(max(0.0, min(1.0, score)), 2)
