"""Twitter API v2 connector for social profile lookup."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ...models.social_profile import SocialProfile

logger = logging.getLogger(__name__)

_TWITTER_API_BASE = "https://api.twitter.com/2"
_USER_FIELDS = "description,public_metrics,profile_image_url,verified,created_at,url"


class TwitterConnector:
    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        self._api_key = api_key
        self._api_secret = api_secret

    async def lookup_profile(self, username: str) -> Optional[SocialProfile]:
        if not self._api_key:
            logger.warning("Twitter API key not configured; skipping lookup for '%s'", username)
            return None

        url = f"{_TWITTER_API_BASE}/users/by/username/{username}"
        params = {"user.fields": _USER_FIELDS}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                logger.debug("Twitter user '%s' not found", username)
                return None

            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", {})

            if not data:
                return None

            metrics = data.get("public_metrics", {})
            return SocialProfile(
                platform="twitter",
                username=data.get("username", username),
                display_name=data.get("name"),
                bio=data.get("description"),
                followers_count=metrics.get("followers_count"),
                following_count=metrics.get("following_count"),
                post_count=metrics.get("tweet_count"),
                is_verified=data.get("verified", False),
                profile_url=f"https://twitter.com/{username}",
                avatar_url=data.get("profile_image_url"),
                raw_data=data,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Twitter API HTTP error for '%s': %s", username, exc)
        except httpx.RequestError as exc:
            logger.error("Twitter API request error for '%s': %s", username, exc)

        return None
