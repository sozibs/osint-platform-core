"""Threat indicator model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class ThreatIndicator(BaseModel):
    model_config = {"populate_by_name": True}

    indicator: str
    indicator_type: str
    threat_type: Optional[str] = None
    severity: str = "unknown"
    confidence: float = 0.0
    sources: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_active: bool = True
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
