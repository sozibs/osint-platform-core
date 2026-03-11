"""API request and response schemas for the Digital Footprint module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class EmailScanRequest(BaseModel):
    email: EmailStr


class PhoneScanRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+?[\d\s\-\(\)]{7,20}$")


class UsernameScanRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


class DomainScanRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253)


class SocialMediaScanRequest(BaseModel):
    platform: str
    username: str


class ScanResponse(BaseModel):
    scan_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    message: str
    scanned_at: datetime
