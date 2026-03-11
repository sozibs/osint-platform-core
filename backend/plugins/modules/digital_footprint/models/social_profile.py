"""Social profile Pydantic model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SocialProfile(BaseModel):
    platform: str
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    is_verified: bool = False
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
