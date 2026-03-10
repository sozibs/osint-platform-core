"""Pattern Detector - identifies recurring patterns across entities."""
from __future__ import annotations
import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects patterns in entity attribute collections."""

    def detect_common_attributes(
        self, entities: list[dict[str, Any]], threshold: float = 0.5
    ) -> dict[str, list[Any]]:
        """Return attributes shared by at least threshold fraction of entities."""
        if not entities:
            return {}
        field_values: dict[str, list[Any]] = {}
        for entity in entities:
            for k, v in entity.get("attributes", {}).items():
                field_values.setdefault(k, []).append(v)
        min_count = max(1, int(len(entities) * threshold))
        return {
            k: list(set(vals))
            for k, vals in field_values.items()
            if len(vals) >= min_count
        }

    def detect_temporal_patterns(
        self, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify recurring time-based patterns in event data."""
        patterns: list[dict[str, Any]] = []
        hour_counts: Counter[int] = Counter()
        for event in events:
            ts = event.get("timestamp", "")
            if "T" in str(ts):
                try:
                    hour = int(str(ts).split("T")[1][:2])
                    hour_counts[hour] += 1
                except (IndexError, ValueError):
                    pass
        for hour, count in hour_counts.most_common(5):
            if count > 1:
                patterns.append({"type": "hourly_peak", "hour": hour, "count": count})
        return patterns
