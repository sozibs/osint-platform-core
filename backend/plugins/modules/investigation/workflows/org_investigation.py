"""Organisation investigation workflow."""

from __future__ import annotations

import logging

from ..connectors.corporate.company_registry import CompanyRegistry
from ..connectors.corporate.sec_filings import SecFilingsConnector
from ..connectors.news.news_aggregator import NewsAggregator
from ..connectors.news.sentiment_analyzer import SentimentAnalyzer
from ..models.org_profile import OrgProfile

logger = logging.getLogger(__name__)


class OrgInvestigation:
    """Orchestrates a full organisation investigation using available data sources."""

    def __init__(self) -> None:
        self._registry = CompanyRegistry()
        self._sec = SecFilingsConnector()
        self._news = NewsAggregator()
        self._sentiment = SentimentAnalyzer()

    async def run(self, org_name: str, jurisdiction: str = "us") -> OrgProfile:
        """Run an investigation for *org_name* and return an :class:`OrgProfile`."""
        logger.info("OrgInvestigation: starting investigation for '%s'", org_name)

        profile = await self._registry.lookup(org_name, jurisdiction)
        if profile is None:
            profile = OrgProfile(name=org_name, jurisdiction=jurisdiction, sources=["basic"])

        # Enrich with SEC filings
        sec_data = await self._sec.search_company(org_name)
        if sec_data:
            hits = sec_data.get("hits", {}).get("hits", [])
            for hit in hits[:10]:
                source = hit.get("_source", {})
                filing_entry = {
                    "form": source.get("form_type"),
                    "date": source.get("file_date"),
                    "description": source.get("display_names", [org_name])[0],
                }
                profile.filings.append(filing_entry)
            if "sec_edgar" not in profile.sources:
                profile.sources.append("sec_edgar")

        # Enrich with news
        mentions = await self._news.search(org_name, max_results=20)
        for mention in mentions:
            text = f"{mention.title} {mention.summary or ''}"
            mention.sentiment = self._sentiment.analyze(text)

        if mentions:
            news_sources = list({m.source for m in mentions if m.source})
            profile.sources.extend(
                s for s in news_sources if s not in profile.sources
            )

        profile.confidence_score = round(
            min(0.3 + len(profile.filings) * 0.05 + len(mentions) * 0.01, 0.95), 2
        )

        logger.info(
            "OrgInvestigation: completed for '%s' — %d filings, %d news mentions",
            org_name,
            len(profile.filings),
            len(mentions),
        )
        return profile
