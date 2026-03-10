"""Input validation and sanitization utilities."""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import unicodedata
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regular expressions
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    re.IGNORECASE,
)

# RFC-3986 URL (http/https/ftp)
_URL_RE = re.compile(
    r"^(https?|ftp)://"
    r"(([a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=]|%[0-9A-Fa-f]{2})+)"
    r"$",
    re.IGNORECASE,
)

# Hostnames / domains
_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}$"
)

# UUID v4 canonical form
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# SQL injection heuristics – common SQL keywords and operators in user input
_SQL_INJECTION_RE = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|EXEC|UNION|"
    r"CAST|CONVERT|DECLARE|FETCH|OPEN|KILL|GRANT|REVOKE|COMMIT|ROLLBACK)\b"
    r"|--|;{2,}|/\*|\*/|xp_|0x[0-9a-fA-F]+)",
    re.IGNORECASE,
)

# XSS heuristics
_XSS_RE = re.compile(
    r"(<script|</script|javascript:|on\w+\s*=|<iframe|<object|<embed|<link|"
    r"data:text/html|vbscript:|expression\()",
    re.IGNORECASE,
)

# Characters that are safe in general string fields
_SAFE_CHARS_RE = re.compile(r"[^\w\s\-.,@/:?&#=+%()'\[\]{}\"!$^*~`|\\<>]", re.UNICODE)

# Valid entity types (mirrors the list in the entities router)
_VALID_ENTITY_TYPES = frozenset(
    {
        "person",
        "organization",
        "location",
        "ip",
        "domain",
        "email",
        "phone",
        "url",
        "hash",
        "cryptocurrency",
        "vehicle",
        "document",
    }
)

# Valid relationship types (broad set; callers can further restrict)
_VALID_RELATIONSHIP_TYPES = frozenset(
    {
        "related_to",
        "associated_with",
        "owns",
        "owned_by",
        "communicates_with",
        "located_at",
        "member_of",
        "alias_of",
        "employed_by",
        "controls",
        "funded_by",
        "linked_to",
        "resolves_to",
        "hosts",
        "registered_by",
        "used_by",
        "part_of",
        "parent_of",
        "child_of",
        "sibling_of",
    }
)


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------


def validate_email(email: str) -> bool:
    """Return ``True`` if *email* looks like a valid e-mail address."""
    if not email or len(email) > 320:
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def validate_url(url: str) -> bool:
    """Return ``True`` if *url* is a syntactically valid http/https/ftp URL."""
    if not url or len(url) > 2_048:
        return False
    return bool(_URL_RE.match(url.strip()))


def validate_ip_address(ip: str) -> bool:
    """
    Return ``True`` if *ip* is a valid IPv4 or IPv6 address.

    Both plain addresses and CIDR notation are accepted.
    """
    if not ip:
        return False
    try:
        ipaddress.ip_network(ip.strip(), strict=False)
        return True
    except ValueError:
        return False


def validate_domain(domain: str) -> bool:
    """Return ``True`` if *domain* is a syntactically valid fully-qualified domain name."""
    if not domain or len(domain) > 253:
        return False
    return bool(_DOMAIN_RE.match(domain.strip().lower()))


def sanitize_string(s: str, max_length: int = 1_024) -> str:
    """
    Strip dangerous characters and truncate to *max_length*.

    Steps
    -----
    1. Normalize unicode to NFC form.
    2. Remove control characters (except tab/newline/carriage-return).
    3. Strip leading/trailing whitespace.
    4. Truncate to *max_length*.

    Parameters
    ----------
    s:
        Input string to sanitize.
    max_length:
        Maximum allowed length of the output string.

    Returns
    -------
    str
        Sanitized string.
    """
    if not s:
        return ""
    # NFC normalization handles homograph attacks
    s = unicodedata.normalize("NFC", s)
    # Remove ASCII control characters except \t \n \r
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    s = s.strip()
    return s[:max_length]


def validate_uuid(uuid_str: str) -> bool:
    """Return ``True`` if *uuid_str* is a valid UUID (any version)."""
    if not uuid_str:
        return False
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False


def validate_json(json_str: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to parse *json_str* as a JSON object.

    Parameters
    ----------
    json_str:
        A JSON-encoded string.

    Returns
    -------
    Optional[Dict[str, Any]]
        Parsed dictionary on success, ``None`` on failure.
    """
    if not json_str:
        return None
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def detect_sql_injection(value: str) -> bool:
    """
    Return ``True`` if *value* contains patterns indicative of SQL injection.

    This is a heuristic filter, not a cryptographic guarantee.
    """
    return bool(_SQL_INJECTION_RE.search(value))


def detect_xss(value: str) -> bool:
    """
    Return ``True`` if *value* contains patterns indicative of XSS payloads.

    This is a heuristic filter, not a cryptographic guarantee.
    """
    return bool(_XSS_RE.search(value))


def validate_entity_type(entity_type: str) -> bool:
    """Return ``True`` if *entity_type* is one of the platform's recognised types."""
    return entity_type.lower() in _VALID_ENTITY_TYPES


def validate_relationship_type(relationship_type: str) -> bool:
    """Return ``True`` if *relationship_type* is a recognised relationship type."""
    return relationship_type.lower() in _VALID_RELATIONSHIP_TYPES


# ---------------------------------------------------------------------------
# Validator class (groups all methods for convenient injection / mocking)
# ---------------------------------------------------------------------------


class InputValidator:
    """
    Centralised input validation and sanitization.

    Wraps the module-level functions so that callers can inject or mock this
    dependency in tests without patching the module namespace.
    """

    def validate_email(self, email: str) -> bool:
        return validate_email(email)

    def validate_url(self, url: str) -> bool:
        return validate_url(url)

    def validate_ip_address(self, ip: str) -> bool:
        return validate_ip_address(ip)

    def validate_domain(self, domain: str) -> bool:
        return validate_domain(domain)

    def sanitize_string(self, s: str, max_length: int = 1_024) -> str:
        return sanitize_string(s, max_length)

    def validate_uuid(self, uuid_str: str) -> bool:
        return validate_uuid(uuid_str)

    def validate_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        return validate_json(json_str)

    def validate_entity_type(self, entity_type: str) -> bool:
        return validate_entity_type(entity_type)

    def validate_relationship_type(self, relationship_type: str) -> bool:
        return validate_relationship_type(relationship_type)

    def detect_sql_injection(self, value: str) -> bool:
        return detect_sql_injection(value)

    def detect_xss(self, value: str) -> bool:
        return detect_xss(value)

    def is_safe_input(self, value: str) -> bool:
        """
        Return ``True`` if *value* passes both SQL-injection and XSS checks.

        Convenience wrapper used in route-level validation.
        """
        return not detect_sql_injection(value) and not detect_xss(value)


# Module-level singleton.
input_validator = InputValidator()
