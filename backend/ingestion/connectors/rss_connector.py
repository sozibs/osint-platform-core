"""RSS and Atom feed connector using feedparser."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)

# Regex patterns reused from web_scraper for entity extraction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HASH_SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
_HASH_SHA1_RE = re.compile(r"\b[0-9a-fA-F]{40}\b")
_HASH_MD5_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")


class RSSConnectorError(Exception):
    """Raised on unrecoverable RSS connector errors."""


class RSSConnector:
    """Async RSS/Atom feed connector with conditional fetching and entity extraction."""

    def __init__(self, rate_limit_per_second: float = 1.0) -> None:
        self.rate_limit = rate_limit_per_second
        self._min_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0
        self._last_fetch_time: float = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            headers={"User-Agent": "OSINTPlatform/1.0 RSS Reader"},
            timeout=httpx.Timeout(30),
            follow_redirects=True,
        )

    # ── Throttle ───────────────────────────────────────────────────────────────

    async def _throttle(self) -> None:
        import time
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_fetch_time)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_fetch_time = time.monotonic()

    # ── Feed fetching ──────────────────────────────────────────────────────────

    async def fetch_feed(
        self,
        url: str,
        last_modified: Optional[datetime] = None,
        etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch and parse RSS/Atom feed with conditional HTTP support.

        Returns a dict with ``feed_info``, ``entries``, ``etag``, ``modified``,
        and ``not_modified`` flag.
        """
        await self._throttle()

        request_headers: Dict[str, str] = {}
        if last_modified:
            request_headers["If-Modified-Since"] = last_modified.strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        if etag:
            request_headers["If-None-Match"] = etag

        try:
            response = await self._client.get(url, headers=request_headers)
        except httpx.RequestError as exc:
            raise RSSConnectorError(f"Network error fetching feed {url}: {exc}") from exc

        if response.status_code == 304:
            return {
                "not_modified": True,
                "feed_info": {},
                "entries": [],
                "etag": etag,
                "modified": last_modified,
            }

        if response.status_code != 200:
            raise RSSConnectorError(
                f"HTTP {response.status_code} when fetching feed {url}"
            )

        raw_etag = response.headers.get("ETag")
        raw_modified = response.headers.get("Last-Modified")
        modified_dt: Optional[datetime] = None
        if raw_modified:
            try:
                modified_dt = parsedate_to_datetime(raw_modified)
            except Exception:
                modified_dt = None

        parsed = feedparser.parse(response.text)

        if parsed.bozo and not parsed.entries:
            raise RSSConnectorError(
                f"Failed to parse feed at {url}: {getattr(parsed, 'bozo_exception', 'unknown error')}"
            )

        feed_info: Dict[str, Any] = {
            "title": getattr(parsed.feed, "title", ""),
            "description": getattr(parsed.feed, "subtitle", ""),
            "link": getattr(parsed.feed, "link", url),
            "language": getattr(parsed.feed, "language", ""),
            "updated": self._parse_date(getattr(parsed.feed, "updated", None)),
        }

        entries = await self.parse_entries({"parsed": parsed, "url": url})

        return {
            "not_modified": False,
            "feed_info": feed_info,
            "entries": entries,
            "etag": raw_etag,
            "modified": modified_dt or last_modified,
        }

    # ── Entry parsing ──────────────────────────────────────────────────────────

    async def parse_entries(self, feed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse feed entries into a normalized list of dicts.

        Each entry: {id, title, url, published, updated, summary, content, author, tags}
        """
        parsed = feed_data.get("parsed")
        feed_url = feed_data.get("url", "")
        if parsed is None:
            return []

        normalized: List[Dict[str, Any]] = []
        for raw_entry in parsed.entries:
            entry_id = getattr(raw_entry, "id", "") or getattr(raw_entry, "link", "")
            title = getattr(raw_entry, "title", "")
            link = getattr(raw_entry, "link", "")
            summary = getattr(raw_entry, "summary", "")
            author = getattr(raw_entry, "author", "")

            # Full content (Atom) vs summary-only (RSS)
            content = ""
            if hasattr(raw_entry, "content") and raw_entry.content:
                content = raw_entry.content[0].get("value", "") if raw_entry.content else ""

            tags: List[str] = [
                t.get("term", "") for t in getattr(raw_entry, "tags", []) if t.get("term")
            ]

            published = self._parse_date(getattr(raw_entry, "published", None))
            updated = self._parse_date(getattr(raw_entry, "updated", None))

            normalized.append({
                "id": entry_id,
                "title": title,
                "url": link,
                "published": published.isoformat() if published else None,
                "updated": updated.isoformat() if updated else None,
                "summary": summary,
                "content": content,
                "author": author,
                "tags": tags,
                "feed_url": feed_url,
            })

        return normalized

    # ── Entity extraction ──────────────────────────────────────────────────────

    async def extract_entities_from_entry(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract OSINT entities from a feed entry's text fields."""
        combined_text = " ".join(
            filter(None, [entry.get("title"), entry.get("summary"), entry.get("content")])
        )
        source_url = entry.get("url", entry.get("feed_url", ""))
        entities: List[Dict[str, Any]] = []

        for match in _EMAIL_RE.finditer(combined_text):
            entities.append({
                "entity_type": "email",
                "value": match.group(0).lower(),
                "source_url": source_url,
            })

        for match in _IP_RE.finditer(combined_text):
            entities.append({
                "entity_type": "ip",
                "value": match.group(0),
                "source_url": source_url,
            })

        for match in _URL_RE.finditer(combined_text):
            from urllib.parse import urlparse
            parsed = urlparse(match.group(0))
            if parsed.netloc:
                entities.append({"entity_type": "url", "value": match.group(0), "source_url": source_url})
                entities.append({"entity_type": "domain", "value": parsed.netloc.lower(), "source_url": source_url})

        for match in _HASH_SHA256_RE.finditer(combined_text):
            entities.append({"entity_type": "hash", "value": match.group(0).lower(), "hash_type": "sha256", "source_url": source_url})

        for match in _HASH_SHA1_RE.finditer(combined_text):
            val = match.group(0).lower()
            if not any(e["value"] == val for e in entities if e["entity_type"] == "hash"):
                entities.append({"entity_type": "hash", "value": val, "hash_type": "sha1", "source_url": source_url})

        for match in _HASH_MD5_RE.finditer(combined_text):
            val = match.group(0).lower()
            if not any(e["value"] == val for e in entities if e["entity_type"] == "hash"):
                entities.append({"entity_type": "hash", "value": val, "hash_type": "md5", "source_url": source_url})

        return entities

    # ── Feed monitoring ────────────────────────────────────────────────────────

    async def monitor_feed(
        self,
        url: str,
        callback: Callable[[List[Dict[str, Any]]], Any],
        check_interval: int = 3600,
    ) -> None:
        """Continuously poll a feed and invoke callback with new entries.

        Runs indefinitely until the task is cancelled. Uses ETag/Last-Modified
        for efficient conditional requests.
        """
        known_ids: set[str] = set()
        etag: Optional[str] = None
        last_modified: Optional[datetime] = None

        logger.info("Starting feed monitor for %s (interval=%ds).", url, check_interval)

        while True:
            try:
                result = await self.fetch_feed(url, last_modified=last_modified, etag=etag)

                if not result.get("not_modified"):
                    etag = result.get("etag") or etag
                    last_modified = result.get("modified") or last_modified

                    new_entries = [
                        e for e in result["entries"] if e["id"] not in known_ids
                    ]

                    if new_entries:
                        logger.info("Found %d new entries in %s.", len(new_entries), url)
                        for entry in new_entries:
                            known_ids.add(entry["id"])
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(new_entries)
                            else:
                                callback(new_entries)
                        except Exception as exc:
                            logger.error("Feed callback error for %s: %s", url, exc)
                    else:
                        logger.debug("No new entries in %s.", url)

            except RSSConnectorError as exc:
                logger.error("Error monitoring feed %s: %s", url, exc)

            except asyncio.CancelledError:
                logger.info("Feed monitor cancelled for %s.", url)
                break

            await asyncio.sleep(check_interval)

    # ── Date parsing ───────────────────────────────────────────────────────────

    def _parse_date(self, date_val: Any) -> Optional[datetime]:
        """Parse various date formats returned by feedparser into a datetime."""
        if date_val is None:
            return None

        if isinstance(date_val, datetime):
            return date_val

        if isinstance(date_val, str):
            from datetime import timezone as tz
            formats = [
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_val.strip(), fmt)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        # feedparser returns time_struct tuples
        if hasattr(date_val, "tm_year"):
            import calendar
            try:
                ts = calendar.timegm(date_val)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

        return None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "RSSConnector":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
