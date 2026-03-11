"""LinkedIn connector stub.

LinkedIn's public API requires OAuth 2.0 on behalf of a signed-in member and
does not permit anonymous profile lookups. A full implementation would require:
  1. An approved LinkedIn Developer application.
  2. User-delegated OAuth 2.0 flow (authorization_code grant).
  3. Access to the Member Data Portability API or Partner Programme endpoints.

Until those credentials are available this connector returns None and logs a
warning so that callers degrade gracefully.
"""

from __future__ import annotations

import logging
from typing import Optional

from ...models.social_profile import SocialProfile

logger = logging.getLogger(__name__)


class LinkedInConnector:
    def __init__(self) -> None:
        pass

    async def lookup_profile(self, username: str) -> Optional[SocialProfile]:
        logger.warning(
            "LinkedIn profile lookup is not available: the LinkedIn API requires "
            "OAuth 2.0 user delegation and an approved Developer application. "
            "Username requested: '%s'",
            username,
        )
        return None
