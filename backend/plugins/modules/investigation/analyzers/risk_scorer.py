"""Risk scorer analyzer."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MAX_SCORE = 1.0
_PUBLIC_RECORDS_WEIGHT = 0.05
_COURT_RECORDS_WEIGHT = 0.15
_NEGATIVE_MEDIA_WEIGHT = 0.10


class RiskScorer:
    """Produces a normalised risk score (0.0 – 1.0) for an investigation profile."""

    def score(self, profile: Dict[str, Any]) -> float:
        """Return a risk score between ``0.0`` and ``1.0`` for *profile*.

        The score is driven by:

        * Number of public records (each contributes :data:`_PUBLIC_RECORDS_WEIGHT`).
        * Number of court records inside ``public_records`` (each contributes
          :data:`_COURT_RECORDS_WEIGHT`).
        * Number of negative media mentions inside ``public_records``
          (each contributes :data:`_NEGATIVE_MEDIA_WEIGHT`).
        """
        raw_score = 0.0

        public_records = profile.get("public_records", [])
        raw_score += len(public_records) * _PUBLIC_RECORDS_WEIGHT

        for record in public_records:
            record_type = (record.get("record_type") or "").lower()
            if "court" in record_type:
                raw_score += _COURT_RECORDS_WEIGHT

            sentiment = (record.get("sentiment") or "").lower()
            if sentiment == "negative":
                raw_score += _NEGATIVE_MEDIA_WEIGHT

        final = round(min(raw_score, _MAX_SCORE), 4)
        logger.debug("RiskScorer: computed score %.4f for profile", final)
        return final
