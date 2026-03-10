"""Data cleaning utilities for OSINT entity normalization."""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_PHONE_STRIP_RE = re.compile(r"[^\d+]")
_PII_MARKERS = re.compile(
    r"\b(ssn|social.?security.?number|credit.?card|cvv|passport.?number)\b",
    re.IGNORECASE,
)

# Disposable email domains (abbreviated sample list)
_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "10minutemail.com", "trashmail.com", "maildrop.cc",
    "sharklasers.com", "guerrillamailblock.com", "spam4.me", "dispostable.com",
}

# Hash type detection by hex length
_HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}


def clean_entity_data(entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and normalize entity attributes by type.

    Returns a new dict with cleaned values; unknown fields are preserved.
    """
    cleaned = {k: v for k, v in data.items() if v is not None}

    if entity_type == "email":
        if "email_address" in cleaned:
            cleaned["email_address"] = normalize_email(str(cleaned["email_address"]))
        if "email" in cleaned:
            cleaned["email"] = normalize_email(str(cleaned["email"]))

    elif entity_type == "ip":
        for key in ("ip_address", "ip", "address"):
            if key in cleaned:
                try:
                    cleaned[key] = normalize_ip_address(str(cleaned[key]))
                except ValueError:
                    pass

    elif entity_type == "hash":
        for key in ("hash_value", "hash", "md5", "sha1", "sha256"):
            if key in cleaned:
                try:
                    norm, htype = normalize_hash(str(cleaned[key]))
                    cleaned["hash_value"] = norm
                    if "hash_type" not in cleaned:
                        cleaned["hash_type"] = htype
                except ValueError:
                    pass

    elif entity_type == "url":
        for key in ("url", "link", "href"):
            if key in cleaned:
                try:
                    cleaned[key] = normalize_url(str(cleaned[key]))
                except ValueError:
                    pass

    elif entity_type == "phone":
        for key in ("phone_number", "phone", "telephone"):
            if key in cleaned:
                normalized = normalize_phone_number(
                    str(cleaned[key]), cleaned.get("country_code")
                )
                if normalized:
                    cleaned[key] = normalized

    elif entity_type in ("person", "organization", "document", "location"):
        for key in ("name", "full_name", "title", "description", "content"):
            if key in cleaned and isinstance(cleaned[key], str):
                cleaned[key] = strip_html(cleaned[key]).strip()

    # Clean aliases list
    if "aliases" in cleaned and isinstance(cleaned["aliases"], list):
        cleaned["aliases"] = deduplicate_aliases(
            [str(a).strip() for a in cleaned["aliases"] if a]
        )

    # Normalize any date fields
    for key in ("birth_date", "registered_at", "expires_at", "created_at",
                "founded_date", "first_seen", "last_seen"):
        if key in cleaned:
            dt = normalize_date(cleaned[key])
            if dt:
                cleaned[key] = dt.isoformat()

    return cleaned


def normalize_phone_number(phone: str, country_code: Optional[str] = None) -> str:
    """Normalize a phone number by stripping non-digit characters.

    Attempts to produce E.164 format. Falls back to digit-only string.
    """
    stripped = _PHONE_STRIP_RE.sub("", phone)
    if phone.startswith("+"):
        stripped = "+" + stripped

    # If no leading +, try to prefix country dial codes
    if not stripped.startswith("+") and country_code:
        dial_codes = {"US": "+1", "GB": "+44", "DE": "+49", "FR": "+33",
                      "AU": "+61", "CA": "+1", "IN": "+91", "CN": "+86"}
        dial = dial_codes.get(country_code.upper(), "")
        if dial and not stripped.startswith(dial.lstrip("+")):
            stripped = dial + stripped

    return stripped if len(stripped) >= 7 else phone.strip()


def normalize_email(email: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return email.strip().lower()


def is_disposable_email(email: str) -> bool:
    """Return True if the email domain is known to be disposable."""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return domain in _DISPOSABLE_DOMAINS


def normalize_ip_address(ip: str) -> str:
    """Normalize an IP address using Python's ipaddress module."""
    return str(ipaddress.ip_address(ip.strip()))


def normalize_hash(hash_val: str) -> Tuple[str, str]:
    """Normalize a hash string and detect its type.

    Returns (normalized_hex, hash_type).
    Raises ValueError if the value is not a recognizable hash.
    """
    normalized = hash_val.strip().lower()
    if not re.match(r"^[0-9a-f]+$", normalized):
        raise ValueError(f"Not a hex hash: {hash_val!r}")
    htype = _HASH_LENGTHS.get(len(normalized))
    if not htype:
        raise ValueError(f"Unrecognized hash length {len(normalized)} for: {hash_val!r}")
    return normalized, htype


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping whitespace and ensuring a scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://", "ftp://")):
        url = "https://" + url
    return url


def remove_pii_markers(text: str) -> str:
    """Redact text that contains PII marker keywords."""
    return _PII_MARKERS.sub("[REDACTED]", text)


def deduplicate_aliases(aliases: List[str]) -> List[str]:
    """Remove duplicate aliases (case-insensitive) while preserving order."""
    seen: set = set()
    result: List[str] = []
    for alias in aliases:
        key = alias.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(alias.strip())
    return result


def strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub(" ", text)


def normalize_date(date_val: Any) -> Optional[datetime]:
    """Parse various date representations into a UTC-aware datetime."""
    if isinstance(date_val, datetime):
        return date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
    if isinstance(date_val, str):
        from normalization.schema.validation_schema import normalize_date_string
        return normalize_date_string(date_val)
    return None
