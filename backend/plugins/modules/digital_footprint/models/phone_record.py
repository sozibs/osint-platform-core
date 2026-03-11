"""Phone record Pydantic model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class PhoneRecord(BaseModel):
    number: str
    country_code: Optional[str] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    is_valid: bool
    region: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
