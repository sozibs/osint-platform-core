"""Email record Pydantic model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class EmailRecord(BaseModel):
    email: str
    is_valid: bool
    is_disposable: bool = False
    domain: str
    breach_count: int = 0
    breaches: List[str] = Field(default_factory=list)
    mx_records: List[str] = Field(default_factory=list)
    reputation_score: float = 0.0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
