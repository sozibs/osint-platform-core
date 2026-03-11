"""News aggregator connector using NewsAPI."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import httpx

from ...models.media_mention import MediaMention

logger = logging.getLogger(__name__)


class NewsAggregator:
    """Fetches news articles from NewsAPI."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 20) -> List[MediaMention]:
        """Search for news articles matching *query*.

        Returns a list of :class:`MediaMention` objects. Requires a valid
        NewsAPI key; returns an empty list with a warning when none is set.
        """
        if not self._api_key:
            logger.warning(
                "NewsAggregator: NEWSAPI_KEY not configured — skipping news search for '%s'",
                query,
            )
            return []

        url = "https://newsapi.org/v2/everything"
        params: Dict[str, Any] = {
            "q": query,
            "apiKey": self._api_key,
            "pageSize": min(max_results, 100),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("NewsAggregator: HTTP error while searching '%s': %s", query, exc)
            return []

        articles = data.get("articles", [])
        mentions: List[MediaMention] = []

        for article in articles:
            source_name: str = (article.get("source") or {}).get("name", "Unknown")
            published_raw: str | None = article.get("publishedAt")
            published_at: datetime | None = None
            if published_raw:
                try:
                    published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass

            mentions.append(
                MediaMention(
                    title=article.get("title") or "",
                    url=article.get("url") or "",
                    source=source_name,
                    published_at=published_at,
                    summary=article.get("description"),
                )
            )

        return mentions
