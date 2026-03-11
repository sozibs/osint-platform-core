"""FactCheck domain model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class FactCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    claim_id: Optional[str] = None
    claim_text: str
    verdict: str
    explanation: Optional[str] = None
    fact_checker: str
    fact_check_url: Optional[str] = None
    published_at: Optional[datetime] = None
    rating: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
