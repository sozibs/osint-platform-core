"""GitHub API connector for social profile lookup."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from ...models.social_profile import SocialProfile

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"


class GitHubConnector:
    def __init__(self, token: str = "") -> None:
        self._token = token

    async def lookup_profile(self, username: str) -> Optional[SocialProfile]:
        url = f"{_GITHUB_API_BASE}/users/{username}"
        headers: dict = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 404:
                logger.debug("GitHub user '%s' not found", username)
                return None

            response.raise_for_status()
            data = response.json()

            created_at: Optional[datetime] = None
            raw_created = data.get("created_at")
            if raw_created:
                try:
                    created_at = datetime.fromisoformat(raw_created.rstrip("Z"))
                except ValueError:
                    pass

            return SocialProfile(
                platform="github",
                username=data.get("login", username),
                display_name=data.get("name"),
                bio=data.get("bio"),
                followers_count=data.get("followers"),
                following_count=data.get("following"),
                post_count=data.get("public_repos"),
                is_verified=False,
                profile_url=data.get("html_url"),
                avatar_url=data.get("avatar_url"),
                created_at=created_at,
                raw_data=data,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("GitHub API HTTP error for '%s': %s", username, exc)
        except httpx.RequestError as exc:
            logger.error("GitHub API request error for '%s': %s", username, exc)

        return None
