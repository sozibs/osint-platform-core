"""Phonetic matching using soundex, metaphone, and NYSIIS algorithms."""
from __future__ import annotations

import logging
from typing import Tuple

import jellyfish

logger = logging.getLogger(__name__)


class PhoneticMatcher:
    """Phonetic string matcher for name disambiguation."""

    def soundex_match(self, s1: str, s2: str) -> bool:
        """Return True if both strings share the same Soundex code."""
        try:
            return jellyfish.soundex(s1) == jellyfish.soundex(s2)
        except Exception:
            return False

    def metaphone_match(self, s1: str, s2: str) -> bool:
        """Return True if both strings share the same Metaphone code."""
        try:
            return jellyfish.metaphone(s1) == jellyfish.metaphone(s2)
        except Exception:
            return False

    def nysiis_match(self, s1: str, s2: str) -> bool:
        """Return True if both strings share the same NYSIIS code."""
        try:
            return jellyfish.nysiis(s1) == jellyfish.nysiis(s2)
        except Exception:
            return False

    def phonetic_score(self, s1: str, s2: str) -> float:
        """Return a 0-1 score based on average of phonetic algorithm matches."""
        if not s1 or not s2:
            return 0.0
        # Use first token for single-algorithm phonetics (handles full names)
        t1 = s1.split()[0] if s1.split() else s1
        t2 = s2.split()[0] if s2.split() else s2
        matches = [
            float(self.soundex_match(t1, t2)),
            float(self.metaphone_match(t1, t2)),
            float(self.nysiis_match(t1, t2)),
        ]
        return sum(matches) / len(matches)

    def is_phonetic_match(
        self, s1: str, s2: str, threshold: float = 0.5
    ) -> Tuple[bool, float]:
        """Return (is_match, phonetic_score) for two strings."""
        score = self.phonetic_score(s1, s2)
        return score >= threshold, score
