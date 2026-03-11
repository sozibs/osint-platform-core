"""Credibility scorer: computes a 0.0–1.0 credibility score for a source."""

from __future__ import annotations

import logging
from typing import List, Optional

from ..models.factcheck import FactCheck
from ..models.source_rating import SourceRating

logger = logging.getLogger(__name__)

_FALSE_VERDICTS = {"false", "mostly false", "pants on fire", "fake", "inaccurate", "misleading"}


class CredibilityScorer:
    """Computes a credibility score for a source domain."""

    def score(
        self,
        source_domain: str,
        source_rating: Optional[SourceRating] = None,
        factchecks: List[FactCheck] = [],
    ) -> float:
        """Return a credibility score between 0.0 (not credible) and 1.0 (highly credible)."""
        credibility = 0.5

        if source_rating is not None:
            credibility = source_rating.credibility_score
            logger.debug(
                "Credibility for %s seeded from SourceRating: %.2f",
                source_domain,
                credibility,
            )

        for fc in factchecks:
            if fc.verdict.lower() in _FALSE_VERDICTS:
                credibility -= 0.1
                logger.debug(
                    "Credibility for %s reduced by false verdict: %s",
                    source_domain,
                    fc.verdict,
                )

        return round(max(0.0, min(credibility, 1.0)), 4)
