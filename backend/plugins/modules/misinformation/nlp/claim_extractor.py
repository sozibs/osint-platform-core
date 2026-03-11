"""Claim extractor: pulls candidate claim sentences from unstructured text."""

from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

_VERB_PATTERNS = re.compile(
    r"\b(is|are|was|were|has|have|had|will|would|could|should|may|might|"
    r"claims|shows|proves|indicates|suggests|reports|states|confirms|denies)\b",
    re.IGNORECASE,
)


class ClaimExtractor:
    """Extracts candidate claim sentences from free text."""

    async def extract(self, text: str) -> List[str]:
        """Return sentences that are likely to be factual claims.

        A sentence is considered a candidate if it:
        - is longer than 10 characters,
        - does not end with a question mark, and
        - contains at least one verb from the claim-verb list.
        """
        sentences = re.split(r"(?<=[.!])\s+", text.strip())
        claims: List[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) <= 10:
                continue
            if sentence.endswith("?"):
                continue
            if _VERB_PATTERNS.search(sentence):
                claims.append(sentence)
                logger.debug("Extracted claim sentence: %s", sentence[:80])
        return claims
