"""MediaMention model."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MediaMention(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    entities_mentioned: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
