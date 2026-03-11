"""API request and response schemas for the Investigation module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PersonSearchRequest(BaseModel):
    full_name: str = Field(..., min_length=2)
    additional_context: Dict[str, Any] = Field(default_factory=dict)


class OrgSearchRequest(BaseModel):
    name: str = Field(..., min_length=2)
    jurisdiction: str = "us"


class CaseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    case_type: str = "person"
    targets: List[Dict[str, Any]] = Field(default_factory=list)


class PublicRecordSearchRequest(BaseModel):
    query: str
    record_type: Optional[str] = None
    jurisdiction: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    case_id: str
    format: str = "json"


class InvestigationResponse(BaseModel):
    id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    message: str
    timestamp: datetime
