"""Validates ingestion sources before they are persisted or polled."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_URL_RE = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)

_REQUIRED_API_FIELDS = {"base_url"}
_REQUIRED_RSS_FIELDS: set[str] = set()
_MAX_FILE_SIZE_DEFAULT_MB = 100


@dataclass
class ValidationResult:
    """Result of a source validation check."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ── URL connectivity ───────────────────────────────────────────────────────────

async def check_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if *url* responds with a non-5xx HTTP status code."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.head(url)
            if response.status_code >= 500:
                # Try GET as fallback (some servers reject HEAD)
                response = await client.get(url)
            return response.status_code < 500
    except Exception as exc:
        logger.debug("URL unreachable %s: %s", url, exc)
        return False


# ── API source validation ──────────────────────────────────────────────────────

async def validate_api_source(
    url: str,
    api_key: Optional[str],
    config: Dict[str, Any],
) -> ValidationResult:
    """Validate an API data source by checking connectivity and config."""
    result = ValidationResult(is_valid=True)

    if not url or not _URL_RE.match(url):
        result.add_error(f"Invalid or missing URL: {url!r}")
        return result

    if not api_key and not config.get("no_auth"):
        result.add_warning("No API key provided; requests may be unauthenticated.")

    reachable = await check_url_reachable(url)
    if not reachable:
        result.add_error(f"URL is not reachable: {url}")
    else:
        result.metadata["reachable"] = True

    if config.get("rate_limit_per_second", 1.0) > 10:
        result.add_warning("Rate limit >10 req/s is aggressive; consider lowering it.")

    if config.get("timeout", 30) > 120:
        result.add_warning("Timeout >120s is unusually high.")

    result.metadata["url"] = url
    result.metadata["authenticated"] = bool(api_key)
    return result


# ── RSS source validation ──────────────────────────────────────────────────────

async def validate_rss_source(url: str) -> ValidationResult:
    """Validate an RSS/Atom feed source."""
    result = ValidationResult(is_valid=True)

    if not url or not _URL_RE.match(url):
        result.add_error(f"Invalid or missing feed URL: {url!r}")
        return result

    reachable = await check_url_reachable(url)
    if not reachable:
        result.add_error(f"Feed URL is not reachable: {url}")
        return result

    # Attempt to actually parse the feed
    try:
        import feedparser

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
        parsed = feedparser.parse(response.text)

        if parsed.bozo and not parsed.entries and not getattr(parsed, "feed", None):
            result.add_error(f"URL does not appear to be a valid RSS/Atom feed: {url}")
        else:
            result.metadata["feed_title"] = getattr(parsed.feed, "title", "")
            result.metadata["entry_count"] = len(parsed.entries)
            result.metadata["feed_version"] = getattr(parsed, "version", "unknown")
    except Exception as exc:
        result.add_warning(f"Could not parse feed content: {exc}")

    result.metadata["url"] = url
    return result


# ── File validation ────────────────────────────────────────────────────────────

async def validate_file(
    file_data: bytes,
    filename: str,
    max_size_mb: float = _MAX_FILE_SIZE_DEFAULT_MB,
) -> ValidationResult:
    """Validate an uploaded file for format support and size constraints."""
    result = ValidationResult(is_valid=True)

    size_mb = len(file_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        result.add_error(
            f"File size {size_mb:.1f} MB exceeds maximum {max_size_mb} MB."
        )

    if not filename:
        result.add_error("Filename is required.")
        return result

    from ingestion.connectors.file_connector import FileConnector

    connector = FileConnector()
    detected = await connector.detect_format(file_data, filename)

    if detected not in connector.SUPPORTED_FORMATS:
        result.add_error(f"Unsupported file format: {detected!r}.")
        return result

    result.metadata["filename"] = filename
    result.metadata["detected_format"] = detected
    result.metadata["size_mb"] = round(size_mb, 2)

    # Try a quick parse to detect corruption
    try:
        records = await connector.ingest(file_data[:65536], filename)
        result.metadata["sample_records"] = len(records)
    except Exception as exc:
        result.add_warning(f"Quick parse check failed (file may be corrupt): {exc}")

    return result


# ── Source config validation ───────────────────────────────────────────────────

def validate_source_config(
    source_type: str, config: Dict[str, Any]
) -> ValidationResult:
    """Validate source-type-specific configuration fields."""
    result = ValidationResult(is_valid=True)

    valid_types = {"api", "rss", "web", "file"}
    if source_type not in valid_types:
        result.add_error(
            f"Unknown source_type '{source_type}'. Valid: {sorted(valid_types)}"
        )
        return result

    if source_type == "api":
        endpoint = config.get("endpoint", "/")
        if not endpoint:
            result.add_warning("No 'endpoint' specified; defaulting to '/'.")

        rate = config.get("rate_limit_per_second", 1.0)
        if not isinstance(rate, (int, float)) or rate <= 0:
            result.add_error("'rate_limit_per_second' must be a positive number.")

    elif source_type == "rss":
        interval = config.get("check_interval", 3600)
        if interval < 60:
            result.add_warning(
                f"Check interval {interval}s is very short; minimum recommended is 60s."
            )

    elif source_type == "web":
        max_depth = config.get("max_depth", 2)
        if max_depth > 5:
            result.add_warning(f"max_depth={max_depth} may be very slow; consider ≤5.")
        if not config.get("respect_robots", True):
            result.add_warning(
                "respect_robots=False disables robots.txt compliance. Ensure this is legal."
            )

    elif source_type == "file":
        mapping = config.get("mapping")
        if mapping and not isinstance(mapping, dict):
            result.add_error("'mapping' must be a dict of {source_field: target_field}.")

    return result
