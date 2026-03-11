"""PersonProfile model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PersonProfile(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    full_name: str
    aliases: List[str] = Field(default_factory=list)
    age: Optional[int] = None
    date_of_birth: Optional[str] = None
    addresses: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    email_addresses: List[str] = Field(default_factory=list)
    social_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    employment_history: List[Dict[str, Any]] = Field(default_factory=list)
    education_history: List[Dict[str, Any]] = Field(default_factory=list)
    public_records: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.0
    sources: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
