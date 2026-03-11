"""Court records connector (stub — no free public API available)."""

from __future__ import annotations

import logging
from typing import List

from ...models.public_record import PublicRecord

logger = logging.getLogger(__name__)


class CourtRecordsConnector:
    """Stub connector for court record searches.

    Court record databases do not offer a free, unified public API.
    Users should perform manual searches on PACER (federal), state court
    portals, or a paid aggregator such as LexisNexis or Thomson Reuters.
    """

    async def search(
        self, query: str, jurisdiction: str = "federal"
    ) -> List[PublicRecord]:
        """Return an empty list and log an informational message.

        Automated retrieval of court records is not supported without a
        paid data provider integration.
        """
        logger.info(
            "CourtRecordsConnector: automated search is not available for query='%s' "
            "jurisdiction='%s'. Please search manually via PACER or a licensed data provider.",
            query,
            jurisdiction,
        )
        return []
