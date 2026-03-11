"""Propagation analyzer: measures how quickly a claim spreads over time."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.claim import Claim

logger = logging.getLogger(__name__)


class PropagationAnalyzer:
    """Analyses the temporal spread of a claim across mention data."""

    async def analyze(
        self, claim: Claim, mentions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Return spread metrics for *claim* based on *mentions*.

        Each mention dict is expected to have a ``timestamp`` or ``created_at``
        key (ISO-8601 string or datetime) and optionally a ``platform`` key.
        """
        if not mentions:
            return {
                "total_mentions": 0,
                "spread_velocity": 0.0,
                "peak_hour": None,
                "timeline": {},
            }

        # Parse and sort timestamps
        parsed: List[datetime] = []
        for m in mentions:
            ts = m.get("timestamp") or m.get("created_at")
            if not ts:
                continue
            try:
                if isinstance(ts, datetime):
                    parsed.append(ts)
                else:
                    parsed.append(datetime.fromisoformat(str(ts)))
            except (ValueError, TypeError):
                logger.debug("Could not parse mention timestamp: %s", ts)

        if not parsed:
            return {
                "total_mentions": len(mentions),
                "spread_velocity": 0.0,
                "peak_hour": None,
                "timeline": {},
            }

        parsed.sort()

        # Build hourly timeline
        timeline: Dict[str, int] = defaultdict(int)
        for ts in parsed:
            hour_key = ts.strftime("%Y-%m-%dT%H:00:00")
            timeline[hour_key] += 1

        peak_hour: Optional[str] = max(timeline, key=lambda k: timeline[k])

        # Spread velocity: mentions per hour over the observed window
        duration_hours = max(
            (parsed[-1] - parsed[0]).total_seconds() / 3600.0, 1.0
        )
        spread_velocity = round(len(parsed) / duration_hours, 4)

        return {
            "total_mentions": len(parsed),
            "spread_velocity": spread_velocity,
            "peak_hour": peak_hour,
            "timeline": dict(sorted(timeline.items())),
        }
