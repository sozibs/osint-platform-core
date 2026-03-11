"""Media Bias / Fact Check (MBFC) connector."""

from __future__ import annotations

import logging
from typing import Optional

from ...models.source_rating import SourceRating

logger = logging.getLogger(__name__)


class MbfcConnector:
    """Connector for Media Bias / Fact Check source ratings.

    MBFC does not provide a public API.  Automated scraping of their website
    may violate their Terms of Service — always review the ToS before
    implementing a scraper.  This connector is a placeholder that returns
    ``None`` to signal that manual lookup is required.
    """

    async def lookup(self, domain: str) -> Optional[SourceRating]:
        """Look up MBFC rating for *domain*.

        Returns ``None`` because MBFC has no public API.  To integrate MBFC
        data, consider manually importing their published CSV datasets or
        obtaining a data-sharing agreement.
        """
        logger.info(
            "MBFC lookup requested for '%s'. MBFC has no public API; "
            "returning None. Review MBFC ToS before implementing a scraper.",
            domain,
        )
        return None
