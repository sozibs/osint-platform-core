"""Claim domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    claim_type: str = "general"
    is_checkworthy: bool = False
    checkworthy_score: float = 0.0
    verified: bool = False
    verdict: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
