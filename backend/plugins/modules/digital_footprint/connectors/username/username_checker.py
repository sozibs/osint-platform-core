"""Username checker: probes common social platforms via HTTP HEAD requests."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import httpx

from ...models.username_record import UsernameRecord

logger = logging.getLogger(__name__)

_PLATFORMS: List[Dict[str, str]] = [
    {"name": "Twitter", "url": "https://twitter.com/{username}"},
    {"name": "GitHub", "url": "https://github.com/{username}"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{username}"},
    {"name": "Instagram", "url": "https://www.instagram.com/{username}/"},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{username}"},
    {"name": "YouTube", "url": "https://www.youtube.com/@{username}"},
    {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{username}"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{username}/"},
    {"name": "Tumblr", "url": "https://{username}.tumblr.com"},
    {"name": "Medium", "url": "https://medium.com/@{username}"},
    {"name": "Dev.to", "url": "https://dev.to/{username}"},
    {"name": "Keybase", "url": "https://keybase.io/{username}"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{username}"},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{username}"},
    {"name": "GitLab", "url": "https://gitlab.com/{username}"},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{username}/"},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{username}"},
    {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={username}"},
    {"name": "ProductHunt", "url": "https://www.producthunt.com/@{username}"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{username}"},
]

_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; osint-platform/1.0)"}


async def _probe_platform(
    client: httpx.AsyncClient,
    platform: Dict[str, str],
    username: str,
) -> Dict[str, Any] | None:
    url = platform["url"].format(username=username)
    try:
        response = await client.head(url, headers=_HEADERS, follow_redirects=True)
        if response.status_code == 200:
            return {"name": platform["name"], "url": url, "status": "found"}
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.debug("Probe failed for %s/%s: %s", platform["name"], username, exc)
    return None


class UsernameChecker:
    async def check(self, username: str) -> UsernameRecord:
        found: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            tasks = [_probe_platform(client, p, username) for p in _PLATFORMS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict):
                found.append(result)

        return UsernameRecord(
            username=username,
            platforms_found=found,
            platforms_checked=len(_PLATFORMS),
        )
