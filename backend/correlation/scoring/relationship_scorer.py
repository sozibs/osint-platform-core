"""Relationship Scorer - computes overall relationship confidence."""
from __future__ import annotations


class RelationshipScorer:
    """Weighted scoring of relationship dimensions."""

    WEIGHTS = {"temporal": 0.25, "behavioral": 0.35, "contextual": 0.40}

    def score(
        self,
        temporal: float,
        behavioral: float,
        contextual: float,
    ) -> float:
        """Return weighted overall score in [0, 1]."""
        return min(
            1.0,
            max(
                0.0,
                self.WEIGHTS["temporal"] * temporal
                + self.WEIGHTS["behavioral"] * behavioral
                + self.WEIGHTS["contextual"] * contextual,
            ),
        )
