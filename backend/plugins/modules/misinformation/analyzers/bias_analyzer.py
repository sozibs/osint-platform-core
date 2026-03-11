"""Bias analyzer: detects political or ideological slant in text."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_LEFT_WORDS: List[str] = ["progressive", "socialist", "liberal", "equity", "justice"]
_RIGHT_WORDS: List[str] = ["conservative", "traditional", "freedom", "patriot", "liberty"]
_NEUTRAL_WORDS: List[str] = ["reported", "according", "stated", "confirmed"]


class BiasAnalyzer:
    """Lexicon-based political bias detector."""

    def analyze(self, text: str) -> Dict[str, Any]:
        """Return a bias score and the words that drove it.

        bias_score ranges from -1.0 (far left) to +1.0 (far right).
        """
        tokens = re.findall(r"[a-zA-Z]+", text.lower())

        left_found: List[str] = [t for t in tokens if t in _LEFT_WORDS]
        right_found: List[str] = [t for t in tokens if t in _RIGHT_WORDS]
        neutral_found: List[str] = [t for t in tokens if t in _NEUTRAL_WORDS]

        left_count = len(left_found)
        right_count = len(right_found)
        total = left_count + right_count

        if total == 0:
            bias_score = 0.0
        else:
            bias_score = round((right_count - left_count) / total, 4)

        return {
            "bias_score": bias_score,
            "detected_words": {
                "left": left_found,
                "right": right_found,
                "neutral": neutral_found,
            },
        }
