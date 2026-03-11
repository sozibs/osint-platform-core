"""PublicRecord model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PublicRecord(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    record_type: str
    title: str
    description: Optional[str] = None
    date: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_url: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
