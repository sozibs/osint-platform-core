"""Narrative domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Narrative(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    claims: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    first_detected: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    spread_score: float = 0.0
    sentiment: str = "neutral"
