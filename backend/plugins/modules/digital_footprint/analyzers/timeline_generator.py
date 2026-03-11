"""Timeline generator: produces a chronological event list from profile data."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATE_FIELDS = (
    ("created_at", "Account created"),
    ("scraped_at", "Profile scraped"),
    ("checked_at", "Record checked"),
)


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


class TimelineGenerator:
    async def generate(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        for profile in profiles:
            platform = profile.get("platform") or profile.get("domain") or "unknown"
            for field, label in _DATE_FIELDS:
                raw = profile.get(field)
                if raw is None:
                    continue
                dt = _parse_dt(raw)
                if dt is None:
                    continue
                events.append(
                    {
                        "timestamp": dt.isoformat(),
                        "event": label,
                        "platform": platform,
                        "details": {
                            k: v
                            for k, v in profile.items()
                            if k not in ("raw_data",) and v is not None
                        },
                    }
                )

        events.sort(key=lambda e: e["timestamp"])
        logger.debug("Timeline generated: %d events from %d profiles", len(events), len(profiles))
        return events
