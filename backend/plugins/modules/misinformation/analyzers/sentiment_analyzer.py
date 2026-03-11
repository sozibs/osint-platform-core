"""Sentiment analyzer: lexicon-based sentiment scoring for text."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_POSITIVE_WORDS: List[str] = [
    "good", "great", "excellent", "positive", "wonderful", "fantastic",
    "outstanding", "beneficial", "success", "win", "best", "love",
    "happy", "hope", "safe", "improve", "support", "trust", "strong",
    "honest", "fair", "help", "progress", "solution", "achieve",
]

_NEGATIVE_WORDS: List[str] = [
    "bad", "terrible", "awful", "negative", "horrible", "dreadful",
    "failure", "lose", "worst", "hate", "sad", "fear", "danger",
    "harmful", "corrupt", "lie", "fraud", "attack", "destroy", "crisis",
    "threat", "wrong", "evil", "fake", "disgrace", "scandal", "collapse",
]


class SentimentAnalyzer:
    """Lexicon-based sentiment analyzer."""

    def analyze(self, text: str) -> Dict[str, Any]:
        """Return sentiment label, score, and matched word lists.

        score ranges from -1.0 (very negative) to +1.0 (very positive).
        """
        tokens = re.findall(r"[a-zA-Z]+", text.lower())

        positive_found: List[str] = [t for t in tokens if t in _POSITIVE_WORDS]
        negative_found: List[str] = [t for t in tokens if t in _NEGATIVE_WORDS]

        pos_count = len(positive_found)
        neg_count = len(negative_found)
        total = pos_count + neg_count

        if total == 0:
            score = 0.0
        else:
            score = round((pos_count - neg_count) / total, 4)

        if score > 0.1:
            sentiment = "positive"
        elif score < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "score": score,
            "positive_words": positive_found,
            "negative_words": negative_found,
        }
