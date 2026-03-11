"""SSL certificate model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Certificate(BaseModel):
    model_config = {"populate_by_name": True}

    domain: str
    subject: Dict[str, Any] = Field(default_factory=dict)
    issuer: Dict[str, Any] = Field(default_factory=dict)
    serial_number: Optional[str] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    san_domains: List[str] = Field(default_factory=list)
    is_expired: bool = False
    is_self_signed: bool = False
    signature_algorithm: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
