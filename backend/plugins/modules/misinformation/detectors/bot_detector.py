"""Bot detector: estimates the probability that a social media account is automated."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BotDetector:
    """Heuristic bot probability scorer based on profile metadata."""

    async def analyze(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return bot probability and a list of supporting indicators."""
        score = 0.0
        indicators: List[str] = []

        # Account age < 30 days
        created_at = profile_data.get("created_at")
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_dt = datetime.fromisoformat(created_at)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                else:
                    created_dt = created_at
                age_days = (datetime.now(timezone.utc) - created_dt).days
                if age_days < 30:
                    score += 0.3
                    indicators.append("account_age_under_30_days")
            except (ValueError, TypeError):
                logger.debug("Could not parse created_at: %s", created_at)

        # Zero followers
        if profile_data.get("followers_count", -1) == 0:
            score += 0.1
            indicators.append("zero_followers")

        # Repeated identical text in recent posts
        posts = profile_data.get("recent_posts", [])
        if posts:
            unique_posts = set(str(p) for p in posts)
            if len(unique_posts) < len(posts):
                score += 0.4
                indicators.append("repeated_identical_content")

        # Username composed entirely of digits
        username = str(profile_data.get("username", ""))
        if username and re.fullmatch(r"\d+", username):
            score += 0.2
            indicators.append("numeric_only_username")

        score = round(min(score, 1.0), 4)
        return {
            "bot_probability": score,
            "indicators": indicators,
            "is_bot": score >= 0.5,
        }
