"""Username record Pydantic model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class UsernameRecord(BaseModel):
    username: str
    platforms_found: List[Dict[str, Any]] = Field(default_factory=list)
    platforms_checked: int = 0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
