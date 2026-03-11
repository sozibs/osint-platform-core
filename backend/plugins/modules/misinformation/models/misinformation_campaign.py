"""MisinformationCampaign domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MisinformationCampaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    narratives: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = "active"
    attribution: Optional[str] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
