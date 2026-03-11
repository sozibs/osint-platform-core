"""Timeline builder analyzer."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TimelineBuilder:
    """Sorts a collection of records into chronological order."""

    async def build(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return *records* sorted by their ``date`` field (ascending).

        Records that have no ``date`` field are appended at the end in their
        original relative order.
        """
        dated = [r for r in records if r.get("date")]
        undated = [r for r in records if not r.get("date")]

        try:
            dated.sort(key=lambda r: r["date"])
        except TypeError:
            logger.warning(
                "TimelineBuilder: mixed date types encountered — falling back to string sort"
            )
            dated.sort(key=lambda r: str(r["date"]))

        timeline = dated + undated

        logger.debug(
            "TimelineBuilder: built timeline with %d dated and %d undated records",
            len(dated),
            len(undated),
        )
        return timeline
