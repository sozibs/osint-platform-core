"""API request and response schemas for the Misinformation module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimDetectRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10000)


class ClaimVerifyRequest(BaseModel):
    claim_id: str
    claim_text: str


class SourceRateRequest(BaseModel):
    domain: str
    name: Optional[str] = None


class NarrativeTrackRequest(BaseModel):
    claims: List[str]
    keywords: List[str] = Field(default_factory=list)


class ContentVerifyRequest(BaseModel):
    url: str
    content_type: str = Field(default="article", pattern="^(article|image|video)$")


class BotDetectRequest(BaseModel):
    profile_data: Dict[str, Any]


class MisinformationResponse(BaseModel):
    id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    message: str
    processed_at: datetime
