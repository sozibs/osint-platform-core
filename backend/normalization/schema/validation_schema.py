"""Pydantic validation schemas with regex patterns and field validators."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator

# ── Regex patterns ─────────────────────────────────────────────────────────────

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    re.IGNORECASE,
)

IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)

IPV6_PATTERN = re.compile(
    r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"
    r"|^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$"
    r"|^[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}$"
    r"|^(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$"
    r"|^(?:[0-9a-fA-F]{1,4}:){1,7}:$"
    r"|^::$",
    re.IGNORECASE,
)

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)

URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)

MD5_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
SHA1_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
SHA512_PATTERN = re.compile(r"^[0-9a-fA-F]{128}$")

PHONE_E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")

# ISO 3166-1 alpha-2 country codes (abbreviated set; full list in production)
_ISO_COUNTRY_CODES = {
    "AF", "AL", "DZ", "AD", "AO", "AG", "AR", "AM", "AU", "AT",
    "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BT",
    "BO", "BA", "BW", "BR", "BN", "BG", "BF", "BI", "CV", "KH",
    "CM", "CA", "CF", "TD", "CL", "CN", "CO", "KM", "CD", "CG",
    "CR", "CI", "HR", "CU", "CY", "CZ", "DK", "DJ", "DM", "DO",
    "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FJ", "FI",
    "FR", "GA", "GM", "GE", "DE", "GH", "GR", "GD", "GT", "GN",
    "GW", "GY", "HT", "HN", "HU", "IS", "IN", "ID", "IR", "IQ",
    "IE", "IL", "IT", "JM", "JP", "JO", "KZ", "KE", "KI", "KP",
    "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI",
    "LT", "LU", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MR",
    "MU", "MX", "FM", "MD", "MC", "MN", "ME", "MA", "MZ", "MM",
    "NA", "NR", "NP", "NL", "NZ", "NI", "NE", "NG", "NO", "OM",
    "PK", "PW", "PA", "PG", "PY", "PE", "PH", "PL", "PT", "QA",
    "RO", "RU", "RW", "KN", "LC", "VC", "WS", "SM", "ST", "SA",
    "SN", "RS", "SC", "SL", "SG", "SK", "SI", "SB", "SO", "ZA",
    "SS", "ES", "LK", "SD", "SR", "SE", "CH", "SY", "TW", "TJ",
    "TZ", "TH", "TL", "TG", "TO", "TT", "TN", "TR", "TM", "TV",
    "UG", "UA", "AE", "GB", "US", "UY", "UZ", "VU", "VE", "VN",
    "YE", "ZM", "ZW",
}

HASH_PATTERNS = {
    "md5": MD5_PATTERN,
    "sha1": SHA1_PATTERN,
    "sha256": SHA256_PATTERN,
    "sha512": SHA512_PATTERN,
}


# ── Validator functions ─────────────────────────────────────────────────────────

def validate_email(email: str) -> str:
    """Validate and normalize an email address string."""
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise ValueError(f"Invalid email address: {email!r}")
    return normalized


def validate_ip_address(ip: str) -> str:
    """Validate an IPv4 or IPv6 address string."""
    ip = ip.strip()
    if IPV4_PATTERN.match(ip) or IPV6_PATTERN.match(ip):
        return ip
    raise ValueError(f"Invalid IP address: {ip!r}")


def validate_domain(domain: str) -> str:
    """Validate a domain name string."""
    domain = domain.strip().lower().rstrip(".")
    if not DOMAIN_PATTERN.match(domain):
        raise ValueError(f"Invalid domain name: {domain!r}")
    return domain


def validate_url(url: str) -> str:
    """Validate a URL string."""
    url = url.strip()
    if not URL_PATTERN.match(url):
        raise ValueError(f"Invalid URL: {url!r}")
    return url


def validate_hash(hash_val: str, hash_type: Optional[str] = None) -> tuple[str, str]:
    """Validate a hash value and detect/verify its type.

    Returns (normalized_hash, detected_type).
    """
    normalized = hash_val.strip().lower()
    if hash_type:
        pattern = HASH_PATTERNS.get(hash_type.lower())
        if pattern and not pattern.match(normalized):
            raise ValueError(f"Hash {hash_val!r} does not match expected {hash_type} format.")
        return normalized, hash_type.lower()

    for htype, pattern in HASH_PATTERNS.items():
        if pattern.match(normalized):
            return normalized, htype

    raise ValueError(f"Cannot determine hash type for value: {hash_val!r}")


def validate_phone_e164(phone: str) -> str:
    """Validate a phone number in E.164 format."""
    phone = phone.strip()
    if not PHONE_E164_PATTERN.match(phone):
        raise ValueError(f"Phone number not in E.164 format: {phone!r}")
    return phone


def validate_country_code(code: str) -> str:
    """Validate an ISO 3166-1 alpha-2 country code."""
    upper = code.strip().upper()
    if upper not in _ISO_COUNTRY_CODES:
        raise ValueError(f"Unknown country code: {code!r}")
    return upper


def validate_coordinates(lat: float, lng: float) -> tuple[float, float]:
    """Validate geographic coordinates."""
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude {lat} out of range [-90, 90].")
    if not (-180.0 <= lng <= 180.0):
        raise ValueError(f"Longitude {lng} out of range [-180, 180].")
    return lat, lng


def normalize_date_string(date_str: Any) -> Optional[datetime]:
    """Attempt to parse a date string into a timezone-aware datetime."""
    if date_str is None:
        return None
    if isinstance(date_str, datetime):
        return date_str if date_str.tzinfo else date_str.replace(tzinfo=timezone.utc)
    if isinstance(date_str, date):
        return datetime(date_str.year, date_str.month, date_str.day, tzinfo=timezone.utc)
    if not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%B %d, %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


# ── Pydantic validation schemas ────────────────────────────────────────────────

class EmailValidationSchema(BaseModel):
    """Strict validation schema for email entities."""

    email_address: str

    @field_validator("email_address")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email(v)


class IPAddressValidationSchema(BaseModel):
    """Strict validation schema for IP address entities."""

    ip_address: str
    ip_version: Optional[int] = None

    @model_validator(mode="after")
    def detect_version(self) -> "IPAddressValidationSchema":
        ip = validate_ip_address(self.ip_address)
        self.ip_address = ip
        if self.ip_version is None:
            self.ip_version = 6 if ":" in ip else 4
        return self


class DomainValidationSchema(BaseModel):
    """Strict validation schema for domain entities."""

    domain: str

    @field_validator("domain")
    @classmethod
    def check_domain(cls, v: str) -> str:
        return validate_domain(v)


class HashValidationSchema(BaseModel):
    """Strict validation schema for hash entities."""

    hash_value: str
    hash_type: Optional[str] = None

    @model_validator(mode="after")
    def detect_hash_type(self) -> "HashValidationSchema":
        normalized, detected = validate_hash(self.hash_value, self.hash_type)
        self.hash_value = normalized
        self.hash_type = detected
        return self


class CoordinateValidationSchema(BaseModel):
    """Validates a latitude/longitude pair."""

    latitude: float
    longitude: float

    @model_validator(mode="after")
    def check_coords(self) -> "CoordinateValidationSchema":
        validate_coordinates(self.latitude, self.longitude)
        return self
