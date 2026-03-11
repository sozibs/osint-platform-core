"""Reddit API connector for social profile lookup."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ...models.social_profile import SocialProfile

logger = logging.getLogger(__name__)

_REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_API_BASE = "https://oauth.reddit.com"
_USER_AGENT = "osint-platform/1.0"


class RedditConnector:
    def __init__(self, client_id: str = "", client_secret: str = "") -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: Optional[str] = None

    async def _get_access_token(self) -> Optional[str]:
        if not self._client_id or not self._client_secret:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    _REDDIT_TOKEN_URL,
                    data={"grant_type": "client_credentials"},
                    auth=(self._client_id, self._client_secret),
                    headers={"User-Agent": _USER_AGENT},
                )
                response.raise_for_status()
                return response.json().get("access_token")
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("Reddit OAuth token request failed: %s", exc)
            return None

    async def lookup_profile(self, username: str) -> Optional[SocialProfile]:
        if not self._client_id or not self._client_secret:
            logger.warning(
                "Reddit credentials not configured; skipping lookup for '%s'", username
            )
            return None

        if not self._access_token:
            self._access_token = await self._get_access_token()

        if not self._access_token:
            return None

        url = f"{_REDDIT_API_BASE}/user/{username}/about"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": _USER_AGENT,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 404:
                logger.debug("Reddit user '%s' not found", username)
                return None

            response.raise_for_status()
            data = response.json().get("data", {})

            return SocialProfile(
                platform="reddit",
                username=data.get("name", username),
                display_name=data.get("subreddit", {}).get("title"),
                bio=data.get("subreddit", {}).get("public_description"),
                followers_count=data.get("total_karma"),
                post_count=data.get("link_karma"),
                is_verified=data.get("verified", False),
                profile_url=f"https://reddit.com/u/{username}",
                avatar_url=data.get("icon_img"),
                raw_data=data,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Reddit API HTTP error for '%s': %s", username, exc)
        except httpx.RequestError as exc:
            logger.error("Reddit API request error for '%s': %s", username, exc)

        return None
