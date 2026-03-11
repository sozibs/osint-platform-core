"""Domain record Pydantic model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DomainRecord(BaseModel):
    domain: str
    registrar: Optional[str] = None
    creation_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    nameservers: List[str] = Field(default_factory=list)
    dns_records: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    reputation_score: float = 0.0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
