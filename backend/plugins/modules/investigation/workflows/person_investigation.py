"""Person investigation workflow."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..connectors.news.news_aggregator import NewsAggregator
from ..connectors.news.sentiment_analyzer import SentimentAnalyzer
from ..models.person_profile import PersonProfile

logger = logging.getLogger(__name__)


class PersonInvestigation:
    """Orchestrates a full person investigation using available data sources."""

    def __init__(self) -> None:
        self._news = NewsAggregator()
        self._sentiment = SentimentAnalyzer()

    async def run(
        self,
        full_name: str,
        additional_context: Dict[str, Any] | None = None,
    ) -> PersonProfile:
        """Run an investigation for *full_name* and return a :class:`PersonProfile`.

        Searches news sources and annotates each mention with a sentiment label.
        """
        if additional_context is None:
            additional_context = {}

        logger.info("PersonInvestigation: starting investigation for '%s'", full_name)

        mentions = await self._news.search(full_name, max_results=20)
        for mention in mentions:
            text = f"{mention.title} {mention.summary or ''}"
            mention.sentiment = self._sentiment.analyze(text)

        sources = list({m.source for m in mentions if m.source})
        confidence = min(0.3 + len(mentions) * 0.02, 0.9) if mentions else 0.1

        profile = PersonProfile(
            full_name=full_name,
            social_profiles=list(additional_context.get("social_profiles", [])),
            public_records=[
                {"title": m.title, "url": m.url, "sentiment": m.sentiment}
                for m in mentions
            ],
            confidence_score=round(confidence, 2),
            sources=sources,
        )

        logger.info(
            "PersonInvestigation: completed for '%s' — %d news mentions found",
            full_name,
            len(mentions),
        )
        return profile
