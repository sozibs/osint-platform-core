"""SSL certificate analyzer using the standard ssl and socket modules."""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List

from ...models.certificate import Certificate

logger = logging.getLogger(__name__)


def _parse_cert_component(component: tuple[tuple[str, str], ...]) -> Dict[str, str]:
    return {k: v for k, v in component}


def _fetch_certificate(domain: str, port: int) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection((domain, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
            return ssock.getpeercert()


class CertAnalyzer:
    """Analyzes SSL/TLS certificates for a given domain and port."""

    async def analyze(self, domain: str, port: int = 443) -> Certificate:
        """Connect to the domain and extract certificate details."""
        loop = asyncio.get_event_loop()
        try:
            cert_dict = await loop.run_in_executor(None, _fetch_certificate, domain, port)
        except ssl.SSLError as exc:
            logger.warning("CertAnalyzer SSL error for %s:%d: %s", domain, port, exc)
            return Certificate(domain=domain)
        except OSError as exc:
            logger.warning("CertAnalyzer connection error for %s:%d: %s", domain, port, exc)
            return Certificate(domain=domain)
        except Exception as exc:
            logger.error("CertAnalyzer unexpected error for %s:%d: %s", domain, port, exc)
            return Certificate(domain=domain)

        subject = _parse_cert_component(cert_dict.get("subject", ()))
        issuer = _parse_cert_component(cert_dict.get("issuer", ()))

        not_before: datetime | None = None
        not_after: datetime | None = None
        fmt = "%b %d %H:%M:%S %Y %Z"
        try:
            nb_str = cert_dict.get("notBefore")
            if nb_str:
                not_before = datetime.strptime(nb_str, fmt)
        except ValueError:
            pass
        try:
            na_str = cert_dict.get("notAfter")
            if na_str:
                not_after = datetime.strptime(na_str, fmt)
        except ValueError:
            pass

        is_expired = bool(not_after and not_after < datetime.now(timezone.utc))
        is_self_signed = subject == issuer

        san_domains: List[str] = []
        for san_type, san_value in cert_dict.get("subjectAltName", ()):
            if san_type == "DNS":
                san_domains.append(san_value)

        return Certificate(
            domain=domain,
            subject=subject,
            issuer=issuer,
            serial_number=str(cert_dict.get("serialNumber")),
            not_before=not_before,
            not_after=not_after,
            san_domains=san_domains,
            is_expired=is_expired,
            is_self_signed=is_self_signed,
            signature_algorithm=cert_dict.get("signatureAlgorithm"),
        )
