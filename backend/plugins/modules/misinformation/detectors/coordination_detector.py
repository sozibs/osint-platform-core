"""Coordination detector: surfaces inauthentic coordinated posting behaviour."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_TIME_WINDOW_SECONDS = 60


class CoordinationDetector:
    """Detects coordinated inauthentic behaviour across a set of posts."""

    async def detect(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse *posts* for coordination signals and return a summary."""
        if not posts:
            return {
                "coordination_score": 0.0,
                "patterns": [],
                "details": {},
            }

        patterns: List[str] = []
        details: Dict[str, Any] = {}

        # Detect near-simultaneous posts
        timestamps = self._parse_timestamps(posts)
        simultaneous_groups = self._find_simultaneous(timestamps)
        if simultaneous_groups:
            patterns.append("simultaneous_posting")
            details["simultaneous_groups"] = simultaneous_groups

        # Detect identical text
        text_map: Dict[str, List[int]] = defaultdict(list)
        for i, post in enumerate(posts):
            text = str(post.get("text", "")).strip()
            if text:
                text_map[text].append(i)
        duplicate_texts = {t: idxs for t, idxs in text_map.items() if len(idxs) > 1}
        if duplicate_texts:
            patterns.append("identical_text")
            details["duplicate_text_count"] = len(duplicate_texts)

        # Detect shared hashtags used by multiple accounts
        hashtag_accounts: Dict[str, set] = defaultdict(set)
        for post in posts:
            account = str(post.get("account_id", post.get("username", "")))
            for tag in post.get("hashtags", []):
                hashtag_accounts[tag].add(account)
        shared_hashtags = {t: list(accs) for t, accs in hashtag_accounts.items() if len(accs) > 1}
        if shared_hashtags:
            patterns.append("shared_hashtags")
            details["shared_hashtags"] = shared_hashtags

        # Compute a simple coordination score
        score = round(min(len(patterns) / 3.0, 1.0), 4)

        return {
            "coordination_score": score,
            "patterns": patterns,
            "details": details,
        }

    def _parse_timestamps(self, posts: List[Dict[str, Any]]) -> List[datetime]:
        timestamps = []
        for post in posts:
            ts = post.get("timestamp") or post.get("created_at")
            if not ts:
                continue
            try:
                if isinstance(ts, datetime):
                    timestamps.append(ts)
                else:
                    timestamps.append(datetime.fromisoformat(str(ts)))
            except (ValueError, TypeError):
                logger.debug("Could not parse timestamp: %s", ts)
        return sorted(timestamps)

    def _find_simultaneous(self, timestamps: List[datetime]) -> List[List[str]]:
        groups: List[List[str]] = []
        i = 0
        while i < len(timestamps):
            group = [timestamps[i].isoformat()]
            j = i + 1
            while j < len(timestamps):
                delta = (timestamps[j] - timestamps[i]).total_seconds()
                if delta <= _TIME_WINDOW_SECONDS:
                    group.append(timestamps[j].isoformat())
                    j += 1
                else:
                    break
            if len(group) > 1:
                groups.append(group)
            i = j if j > i + 1 else i + 1
        return groups
