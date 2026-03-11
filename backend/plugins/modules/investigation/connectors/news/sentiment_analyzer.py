"""Simple keyword-based sentiment analyzer."""

from __future__ import annotations

_POSITIVE_WORDS = {"good", "great", "excellent", "positive", "success"}
_NEGATIVE_WORDS = {"bad", "terrible", "scandal", "fraud", "criminal", "lawsuit"}


class SentimentAnalyzer:
    """Classifies text sentiment using keyword matching."""

    def analyze(self, text: str) -> str:
        """Return ``"positive"``, ``"negative"``, or ``"neutral"`` for *text*."""
        lowered = text.lower()
        words = set(lowered.split())

        positive_hits = len(words & _POSITIVE_WORDS)
        negative_hits = len(words & _NEGATIVE_WORDS)

        if negative_hits > positive_hits:
            return "negative"
        if positive_hits > negative_hits:
            return "positive"
        return "neutral"
