"""Narrative detector: groups related claims into thematic narratives."""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Set

from ..models.claim import Claim
from ..models.narrative import Narrative

logger = logging.getLogger(__name__)

_STOP_WORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "it", "its", "this", "that", "they", "their",
    "we", "our", "you", "your", "he", "she", "his", "her", "not", "as",
    "if", "so", "do", "did", "will", "can", "could", "would", "should",
}


def _keywords_from_text(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


class NarrativeDetector:
    """Groups claims with shared keywords into narrative objects."""

    async def detect(
        self, claims: List[Claim], keywords: List[str] = []
    ) -> List[Narrative]:
        """Cluster *claims* by shared keywords and return detected narratives."""
        if not claims:
            return []

        # Build per-claim keyword sets
        claim_keywords: Dict[str, List[str]] = {}
        all_word_counts: Counter = Counter()
        for claim in claims:
            kws = _keywords_from_text(claim.text)
            claim_keywords[claim.id] = kws
            all_word_counts.update(kws)

        # Global seed keywords: user-supplied + most frequent corpus words
        seed_keywords: List[str] = list(keywords)
        seed_keywords += [w for w, _ in all_word_counts.most_common(10)]
        seed_set = set(seed_keywords)

        # Group claims that share at least one seed keyword
        grouped: Dict[str, List[Claim]] = {}
        ungrouped: List[Claim] = []
        for claim in claims:
            shared = seed_set & set(claim_keywords[claim.id])
            if shared:
                key = sorted(shared)[0]
                grouped.setdefault(key, []).append(claim)
            else:
                ungrouped.append(claim)

        # Build narratives for each group
        narratives: List[Narrative] = []
        for keyword, group_claims in grouped.items():
            all_kws: Counter = Counter()
            for c in group_claims:
                all_kws.update(claim_keywords[c.id])
            top_kws = [w for w, _ in all_kws.most_common(10)]
            narrative = Narrative(
                title=f"Narrative around '{keyword}'",
                description=f"Cluster of {len(group_claims)} claims sharing the theme '{keyword}'.",
                claims=[c.id for c in group_claims],
                keywords=top_kws,
                first_detected=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
            narratives.append(narrative)
            logger.debug("Detected narrative '%s' with %d claims", keyword, len(group_claims))

        # Collect remaining claims into a catch-all narrative if any
        if ungrouped:
            narrative = Narrative(
                title="Miscellaneous claims",
                description=f"{len(ungrouped)} claims without a dominant shared theme.",
                claims=[c.id for c in ungrouped],
                keywords=[],
                first_detected=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
            narratives.append(narrative)

        return narratives
