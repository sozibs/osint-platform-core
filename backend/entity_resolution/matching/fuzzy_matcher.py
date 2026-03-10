"""Fuzzy string matching using Levenshtein and Jaro-Winkler algorithms."""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import Levenshtein
import jellyfish

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """Multi-algorithm fuzzy string matcher for entity name comparison."""

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold

    def levenshtein_similarity(self, s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        distance = Levenshtein.distance(s1.lower(), s2.lower())
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len) if max_len > 0 else 1.0

    def jaro_winkler_similarity(self, s1: str, s2: str) -> float:
        return jellyfish.jaro_winkler_similarity(s1.lower(), s2.lower())

    def token_sort_ratio(self, s1: str, s2: str) -> float:
        t1 = " ".join(sorted(s1.lower().split()))
        t2 = " ".join(sorted(s2.lower().split()))
        return self.levenshtein_similarity(t1, t2)

    def combined_score(self, s1: str, s2: str) -> float:
        lev = self.levenshtein_similarity(s1, s2)
        jw = self.jaro_winkler_similarity(s1, s2)
        tsr = self.token_sort_ratio(s1, s2)
        return 0.3 * lev + 0.4 * jw + 0.3 * tsr

    def find_best_match(
        self, query: str, candidates: List[str]
    ) -> Optional[Tuple[str, float]]:
        """Find the best matching string from candidates list."""
        if not candidates:
            return None
        scored = [(c, self.combined_score(query, c)) for c in candidates]
        best = max(scored, key=lambda x: x[1])
        return best if best[1] > 0 else None

    def find_matches_above_threshold(
        self,
        query: str,
        candidates: List[str],
        threshold: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """Return all candidates with combined score above threshold."""
        t = threshold if threshold is not None else self.threshold
        results = [
            (c, self.combined_score(query, c))
            for c in candidates
            if self.combined_score(query, c) >= t
        ]
        return sorted(results, key=lambda x: x[1], reverse=True)

    def are_likely_same(self, s1: str, s2: str) -> Tuple[bool, float]:
        """Determine if two strings likely refer to the same entity."""
        score = self.combined_score(s1, s2)
        return score >= self.threshold, score
