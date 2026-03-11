"""Threat scorer — computes a composite threat score from threat indicators."""

from __future__ import annotations

import logging
from typing import List

from ..models.threat_indicator import ThreatIndicator

logger = logging.getLogger(__name__)


class ThreatScorer:
    """Computes a weighted threat score across multiple threat indicators."""

    def score(self, indicators: List[ThreatIndicator]) -> float:
        """Return a weighted average confidence score in the range 0.0–1.0.

        Indicators with higher severity carry greater weight in the average.
        """
        if not indicators:
            return 0.0

        _SEVERITY_WEIGHTS = {
            "high": 3.0,
            "medium": 2.0,
            "low": 1.0,
            "clean": 0.5,
            "unknown": 1.0,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for indicator in indicators:
            weight = _SEVERITY_WEIGHTS.get(indicator.severity.lower(), 1.0)
            weighted_sum += indicator.confidence * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0

        return min(1.0, weighted_sum / total_weight)
