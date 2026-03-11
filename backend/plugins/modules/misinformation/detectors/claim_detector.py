"""Claim detector: identifies checkworthy claims in free text."""

from __future__ import annotations

import logging
import re
from typing import List

from ..models.claim import Claim

logger = logging.getLogger(__name__)

_CLAIM_INDICATORS = [
    "claims",
    "reportedly",
    "according to",
    "it is alleged",
    "sources say",
    "officials claim",
    "studies show",
    "experts say",
    "it is believed",
]


class ClaimDetector:
    """Detects and scores checkworthy claims in unstructured text."""

    async def detect(self, text: str) -> List[Claim]:
        """Split *text* into sentences and return checkworthy claims."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        claims: List[Claim] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            score = self._checkworthy_score(sentence)
            if score > 0.3:
                claim = Claim(
                    text=sentence,
                    is_checkworthy=True,
                    checkworthy_score=round(min(score, 1.0), 4),
                )
                claims.append(claim)
                logger.debug("Detected claim (score=%.2f): %s", score, sentence[:80])
        return claims

    def _checkworthy_score(self, sentence: str) -> float:
        score = 0.0
        lower = sentence.lower()

        if re.search(r"\d", sentence):
            score += 0.2

        if any(indicator in lower for indicator in _CLAIM_INDICATORS):
            score += 0.3

        if len(sentence) > 20:
            score += 0.1

        if "?" in sentence:
            score -= 0.1
            score += 0.05  # slight bump for rhetorical questions still worth checking

        return score
