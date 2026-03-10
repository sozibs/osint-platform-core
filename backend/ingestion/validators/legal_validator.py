"""Legal and ethical validation for OSINT data sources."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = "OSINTPlatform/1.0 (research; contact: admin@example.com)"

# Known public-data domains that are generally freely accessible
_PUBLIC_DATA_DOMAINS = {
    "data.gov", "data.europa.eu", "opendata.gov.uk", "data.gov.au",
    "census.gov", "sec.gov", "irs.gov", "fbi.gov", "archives.gov",
    "github.com", "gitlab.com", "bitbucket.org",
    "shodan.io", "virustotal.com", "otx.alienvault.com",
    "abuse.ch", "threatfox.abuse.ch", "feodotracker.abuse.ch",
    "urlhaus.abuse.ch", "sslbl.abuse.ch",
    "wikipedia.org", "wikidata.org",
    "whois.iana.org", "rdap.iana.org",
    "pastebin.com",
}

# Domains that require additional care / are known to restrict access
_RESTRICTED_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "tiktok.com", "snapchat.com", "pinterest.com",
}

# Patterns indicating potentially sensitive data categories
_SENSITIVE_PATTERNS = [
    re.compile(r"\b(ssn|social.?security)\b", re.IGNORECASE),
    re.compile(r"\b(credit.?card|cc.?number|cvv)\b", re.IGNORECASE),
    re.compile(r"\b(passport|national.?id)\b", re.IGNORECASE),
    re.compile(r"\b(medical|health.?record|diagnosis)\b", re.IGNORECASE),
    re.compile(r"\b(biometric|fingerprint|face.?id)\b", re.IGNORECASE),
]


class SensitivityLevel(str, Enum):
    """Classification of data sensitivity."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    HIGHLY_SENSITIVE = "highly_sensitive"
    RESTRICTED = "restricted"


@dataclass
class ToSCheckResult:
    """Result of a Terms of Service inspection."""

    url: str
    tos_url: Optional[str] = None
    scraping_mentioned: bool = False
    scraping_prohibited: Optional[bool] = None
    automated_access_prohibited: Optional[bool] = None
    notes: str = ""


@dataclass
class LegalValidationResult:
    """Result of legal/ethical validation for a data source."""

    is_legal: bool
    restrictions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_consent: bool = False
    sensitivity_level: SensitivityLevel = SensitivityLevel.PUBLIC
    robots_txt_compliant: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_restriction(self, msg: str) -> None:
        self.restrictions.append(msg)
        self.is_legal = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ── robots.txt ─────────────────────────────────────────────────────────────────

async def check_robots_txt(url: str) -> bool:
    """Return True if the URL is allowed by the domain's robots.txt."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"

    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(robots_url)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            return True  # No robots.txt → assume allowed
    except Exception as exc:
        logger.debug("Could not fetch robots.txt for %s: %s", base, exc)
        return True

    return bool(parser.can_fetch(_USER_AGENT, url))


# ── Terms of Service ───────────────────────────────────────────────────────────

async def check_terms_of_service(url: str) -> ToSCheckResult:
    """Heuristically inspect a site's Terms of Service for scraping prohibitions.

    Fetches common ToS URLs and scans for relevant keywords.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    result = ToSCheckResult(url=url)

    tos_candidates = [
        f"{base}/terms",
        f"{base}/terms-of-service",
        f"{base}/tos",
        f"{base}/legal/terms",
        f"{base}/about/legal",
    ]

    _prohibit_patterns = [
        re.compile(r"\b(no|not|prohibit|forbid|restrict|shall not|must not).{0,40}(scrape|crawl|harvest|automat)", re.IGNORECASE),
        re.compile(r"\b(scraping|crawling|harvesting|automated.access).{0,30}(not|prohibit|allow|forbid)", re.IGNORECASE),
    ]
    _mention_patterns = [
        re.compile(r"\b(scrape|crawl|harvest|bot|spider|automat)", re.IGNORECASE),
    ]

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for tos_url in tos_candidates:
            try:
                response = await client.get(tos_url)
                if response.status_code == 200 and len(response.text) > 200:
                    result.tos_url = tos_url
                    text = response.text

                    result.scraping_mentioned = bool(_mention_patterns[0].search(text))
                    for pat in _prohibit_patterns:
                        if pat.search(text):
                            result.scraping_prohibited = True
                            result.automated_access_prohibited = True
                            break
                    else:
                        result.scraping_prohibited = False
                    break
            except Exception:
                continue

    return result


# ── Public source check ────────────────────────────────────────────────────────

def is_public_source(url: str) -> bool:
    """Return True if the URL's domain is known to provide public data."""
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith(f".{d}") for d in _PUBLIC_DATA_DOMAINS)


# ── Data sensitivity ───────────────────────────────────────────────────────────

def check_data_sensitivity(data: Dict[str, Any]) -> SensitivityLevel:
    """Classify the sensitivity level of a data dict by examining its content."""
    text = " ".join(str(v) for v in data.values())

    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return SensitivityLevel.HIGHLY_SENSITIVE

    # Check field names
    field_names = " ".join(str(k) for k in data.keys()).lower()
    if any(kw in field_names for kw in ("password", "secret", "token", "private_key", "api_key")):
        return SensitivityLevel.RESTRICTED

    if any(kw in field_names for kw in ("email", "phone", "address", "dob", "birth")):
        return SensitivityLevel.SENSITIVE

    if any(kw in field_names for kw in ("name", "username", "user_id", "profile")):
        return SensitivityLevel.INTERNAL

    return SensitivityLevel.PUBLIC


# ── Consent check ──────────────────────────────────────────────────────────────

def validate_data_collection_consent(source_config: Dict[str, Any]) -> bool:
    """Return True if the source config explicitly acknowledges consent requirements."""
    return bool(
        source_config.get("consent_acknowledged")
        or source_config.get("legal_confirmed")
        or source_config.get("public_data", False)
    )


# ── Main legal validation ──────────────────────────────────────────────────────

async def validate_source_legality(
    url: str, source_type: str
) -> LegalValidationResult:
    """Perform comprehensive legal/ethical validation for a data source.

    Checks robots.txt, known restricted domains, ToS (for web sources),
    and whether the source is public data.
    """
    result = LegalValidationResult(is_legal=True)
    parsed = urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")

    # Check known restricted domains
    if any(domain == d or domain.endswith(f".{d}") for d in _RESTRICTED_DOMAINS):
        result.add_restriction(
            f"Domain {domain!r} is known to restrict automated access. "
            "Review their ToS and API terms before collecting data."
        )
        result.requires_consent = True

    # robots.txt check
    robots_ok = await check_robots_txt(url)
    result.robots_txt_compliant = robots_ok
    if not robots_ok:
        result.add_warning(
            f"robots.txt disallows crawling this URL: {url}. "
            "Proceeding may violate the site's policies."
        )

    # For web scraping, check ToS
    if source_type == "web":
        tos_result = await check_terms_of_service(url)
        result.metadata["tos"] = {
            "tos_url": tos_result.tos_url,
            "scraping_mentioned": tos_result.scraping_mentioned,
            "scraping_prohibited": tos_result.scraping_prohibited,
        }
        if tos_result.scraping_prohibited:
            result.add_restriction(
                f"Terms of Service at {tos_result.tos_url} appear to prohibit scraping."
            )

    # Public data bonus
    if is_public_source(url):
        result.metadata["is_known_public_source"] = True
    else:
        result.add_warning(
            "Source is not in the known public-data list. Manually verify legality."
        )

    result.metadata["url"] = url
    result.metadata["source_type"] = source_type
    result.metadata["domain"] = domain
    return result
