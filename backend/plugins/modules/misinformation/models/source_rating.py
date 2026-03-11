"""SourceRating domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceRating(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    domain: str
    name: Optional[str] = None
    bias_rating: Optional[str] = None
    factual_reporting: Optional[str] = None
    credibility_score: float = 0.5
    country: Optional[str] = None
    media_type: Optional[str] = None
    notes: Optional[str] = None
    source: str = "manual"
    rated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
