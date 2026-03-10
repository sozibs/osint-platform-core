"""Pydantic models for API key request and response payloads."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """Payload for generating a new API key."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable label for the API key",
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="List of permission strings granted to this key",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional UTC datetime when the key expires",
    )


class ApiKeyResponse(BaseModel):
    """API key metadata returned by list/get endpoints (raw key is NOT included)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    permissions: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class ApiKeyCreateResponse(BaseModel):
    """
    Response returned **only** on key creation.

    Contains the raw ``key`` field that must be presented to the user exactly
    once.  It is never stored in plain text and cannot be retrieved later.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    permissions: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    key: str = Field(..., description="Raw API key — shown only once on creation")
