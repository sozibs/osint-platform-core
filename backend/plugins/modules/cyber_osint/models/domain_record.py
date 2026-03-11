"""Domain record model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class CyberDomainRecord(BaseModel):
    model_config = {"populate_by_name": True}

    domain: str
    registrar: Optional[str] = None
    creation_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    nameservers: List[str] = Field(default_factory=list)
    a_records: List[str] = Field(default_factory=list)
    mx_records: List[str] = Field(default_factory=list)
    txt_records: List[str] = Field(default_factory=list)
    ns_records: List[str] = Field(default_factory=list)
    subdomains: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    reputation_score: float = 0.0
    is_malicious: bool = False
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
