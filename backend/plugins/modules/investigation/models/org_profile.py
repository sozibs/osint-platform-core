"""OrgProfile model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OrgProfile(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    aliases: List[str] = Field(default_factory=list)
    registration_number: Optional[str] = None
    jurisdiction: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    founded_date: Optional[str] = None
    status: Optional[str] = None
    officers: List[Dict[str, Any]] = Field(default_factory=list)
    subsidiaries: List[str] = Field(default_factory=list)
    addresses: List[str] = Field(default_factory=list)
    filings: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.0
    sources: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
