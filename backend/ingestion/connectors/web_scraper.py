"""Ethical web scraper with robots.txt compliance and rate limiting."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Regex patterns for entity extraction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,5}"
)
_IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_CRYPTO_BTC_RE = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
_HASH_MD5_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")
_HASH_SHA1_RE = re.compile(r"\b[0-9a-fA-F]{40}\b")
_HASH_SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")

_DEFAULT_USER_AGENT = "OSINTPlatform/1.0 (research; contact: admin@example.com)"


class WebScraperError(Exception):
    """Raised on unrecoverable scraper errors."""


class EthicalWebScraper:
    """Ethical, rate-limited web scraper with robots.txt compliance."""

    def __init__(
        self,
        rate_limit_per_second: float = 0.5,
        user_agent: str = _DEFAULT_USER_AGENT,
        respect_robots: bool = True,
        max_depth: int = 2,
    ) -> None:
        self.rate_limit = rate_limit_per_second
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.max_depth = max_depth
        self._min_interval = 1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0
        self._robots_cache: Dict[str, RobotFileParser] = {}
        self._last_request_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(30),
            follow_redirects=True,
        )

    # ── Rate limiting ──────────────────────────────────────────────────────────

    async def _throttle(self, domain: str) -> None:
        """Per-domain rate limiter."""
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            last = self._last_request_times.get(domain, 0.0)
            wait = self._min_interval - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_times[domain] = time.monotonic()

    # ── robots.txt ────────────────────────────────────────────────────────────

    async def _fetch_robots(self, base_url: str) -> RobotFileParser:
        """Fetch and cache the robots.txt for a given base URL."""
        robots_url = urljoin(base_url, "/robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = await self._client.get(robots_url)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                parser.parse([])
        except Exception as exc:
            logger.warning("Could not fetch robots.txt from %s: %s", robots_url, exc)
            parser.parse([])
        return parser

    async def can_fetch(self, url: str) -> bool:
        """Return True if the URL can be fetched according to robots.txt."""
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            self._robots_cache[base] = await self._fetch_robots(base)
        try:
            return self._robots_cache[base].can_fetch(self.user_agent, url)
        except Exception:
            return True

    # ── Page scraping ──────────────────────────────────────────────────────────

    async def scrape_page(self, url: str) -> Dict[str, Any]:
        """Scrape a single page and return structured data.

        Returns a dict with keys: url, title, text, links, metadata, scraped_at.
        """
        import datetime

        parsed = urlparse(url)
        domain = parsed.netloc

        if not await self.can_fetch(url):
            logger.info("robots.txt disallows scraping: %s", url)
            return {
                "url": url,
                "blocked_by_robots": True,
                "title": None,
                "text": "",
                "links": [],
                "metadata": {},
                "scraped_at": datetime.datetime.utcnow().isoformat(),
            }

        await self._throttle(domain)

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("HTTP error scraping %s: %s", url, exc)
            raise WebScraperError(f"Failed to scrape {url}: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            logger.debug("Skipping non-HTML content at %s (%s)", url, content_type)
            return {
                "url": url,
                "title": None,
                "text": "",
                "links": [],
                "metadata": {"content_type": content_type},
                "scraped_at": datetime.datetime.utcnow().isoformat(),
            }

        soup = BeautifulSoup(response.text, "lxml")

        # Remove script and style elements
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Extract text
        text = soup.get_text(separator=" ", strip=True)

        # Extract all links
        links: List[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            abs_href = urljoin(url, href)
            parsed_href = urlparse(abs_href)
            if parsed_href.scheme in ("http", "https"):
                links.append(abs_href)

        # Extract metadata
        metadata: Dict[str, Any] = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property", "")
            content = meta.get("content", "")
            if name and content:
                metadata[name.lower()] = content

        return {
            "url": url,
            "title": title,
            "text": text,
            "links": list(set(links)),
            "metadata": metadata,
            "scraped_at": datetime.datetime.utcnow().isoformat(),
        }

    # ── Entity extraction ──────────────────────────────────────────────────────

    async def extract_entities(self, text: str, url: str) -> List[Dict[str, Any]]:
        """Extract potential OSINT entities from text using regex patterns."""
        entities: List[Dict[str, Any]] = []

        for match in _EMAIL_RE.finditer(text):
            entities.append({
                "entity_type": "email",
                "value": match.group(0).lower(),
                "source_url": url,
                "context": text[max(0, match.start() - 40): match.end() + 40],
            })

        for match in _IP_RE.finditer(text):
            entities.append({
                "entity_type": "ip",
                "value": match.group(0),
                "source_url": url,
                "context": text[max(0, match.start() - 40): match.end() + 40],
            })

        for match in _URL_RE.finditer(text):
            parsed = urlparse(match.group(0))
            if parsed.netloc:
                entities.append({
                    "entity_type": "url",
                    "value": match.group(0),
                    "source_url": url,
                    "context": "",
                })
                entities.append({
                    "entity_type": "domain",
                    "value": parsed.netloc.lower(),
                    "source_url": url,
                    "context": "",
                })

        for match in _PHONE_RE.finditer(text):
            val = re.sub(r"\s+", "", match.group(0))
            if len(val) >= 7:
                entities.append({
                    "entity_type": "phone",
                    "value": val,
                    "source_url": url,
                    "context": text[max(0, match.start() - 30): match.end() + 30],
                })

        for match in _HASH_SHA256_RE.finditer(text):
            entities.append({
                "entity_type": "hash",
                "value": match.group(0).lower(),
                "hash_type": "sha256",
                "source_url": url,
                "context": "",
            })

        for match in _HASH_SHA1_RE.finditer(text):
            val = match.group(0).lower()
            if not any(e["value"] == val for e in entities if e["entity_type"] == "hash"):
                entities.append({
                    "entity_type": "hash",
                    "value": val,
                    "hash_type": "sha1",
                    "source_url": url,
                    "context": "",
                })

        for match in _HASH_MD5_RE.finditer(text):
            val = match.group(0).lower()
            if not any(e["value"] == val for e in entities if e["entity_type"] == "hash"):
                entities.append({
                    "entity_type": "hash",
                    "value": val,
                    "hash_type": "md5",
                    "source_url": url,
                    "context": "",
                })

        for match in _CRYPTO_BTC_RE.finditer(text):
            entities.append({
                "entity_type": "cryptocurrency",
                "value": match.group(0),
                "currency_type": "bitcoin",
                "source_url": url,
                "context": "",
            })

        return entities

    # ── BFS crawl ──────────────────────────────────────────────────────────────

    async def scrape_with_depth(
        self, start_url: str, max_pages: int = 10
    ) -> List[Dict[str, Any]]:
        """BFS crawl from start_url up to max_depth and max_pages."""
        visited: Set[str] = set()
        results: List[Dict[str, Any]] = []
        # Queue entries: (url, depth)
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        base_domain = urlparse(start_url).netloc

        while queue and len(results) < max_pages:
            current_url, depth = queue.popleft()

            if current_url in visited:
                continue
            visited.add(current_url)

            if depth > self.max_depth:
                continue

            try:
                page_data = await self.scrape_page(current_url)
                page_data["depth"] = depth
                results.append(page_data)
                logger.debug("Scraped %s (depth=%d).", current_url, depth)
            except WebScraperError as exc:
                logger.warning("Skipping %s: %s", current_url, exc)
                continue

            if depth < self.max_depth:
                for link in page_data.get("links", []):
                    parsed_link = urlparse(link)
                    if parsed_link.netloc == base_domain and link not in visited:
                        queue.append((link, depth + 1))

        return results

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
        logger.debug("EthicalWebScraper HTTP client closed.")

    async def __aenter__(self) -> "EthicalWebScraper":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
