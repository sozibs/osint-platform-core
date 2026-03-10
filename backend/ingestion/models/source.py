"""Pydantic models for data sources."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# ── Source type configs ────────────────────────────────────────────────────────

class APISourceConfig(BaseModel):
    """Configuration specific to an HTTP API source."""

    endpoint: str = Field(default="/", description="API endpoint path or full URL")
    api_key: Optional[str] = Field(default=None, description="API key / bearer token")
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=300)
    rate_limit_per_second: float = Field(default=1.0, gt=0, le=100)
    paginated: bool = Field(default=True)
    page_param: str = Field(default="page")
    page_size_param: str = Field(default="per_page")
    page_size: int = Field(default=100, ge=1, le=10000)
    cursor_based: bool = Field(default=False)
    cursor_param: str = Field(default="cursor")
    no_auth: bool = Field(default=False, description="Explicitly mark as unauthenticated")


class RSSSourceConfig(BaseModel):
    """Configuration specific to an RSS/Atom feed source."""

    check_interval: int = Field(default=3600, ge=60, description="Poll interval in seconds")
    rate_limit_per_second: float = Field(default=1.0, gt=0)
    etag: Optional[str] = Field(default=None)
    last_modified: Optional[str] = Field(default=None)
    extract_entities: bool = Field(default=True)


class WebSourceConfig(BaseModel):
    """Configuration specific to a web scraping source."""

    rate_limit_per_second: float = Field(default=0.5, gt=0, le=5.0)
    max_depth: int = Field(default=2, ge=0, le=10)
    max_pages: int = Field(default=20, ge=1, le=500)
    respect_robots: bool = Field(default=True)
    user_agent: str = Field(
        default="OSINTPlatform/1.0 (research; contact: admin@example.com)"
    )
    allowed_domains: List[str] = Field(
        default_factory=list, description="Restrict crawl to these domains"
    )


class FileSourceConfig(BaseModel):
    """Configuration specific to a file ingestion source."""

    mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Field mapping: {source_field: target_field}",
    )
    delimiter: str = Field(default=",", max_length=1)
    encoding: str = Field(default="utf-8")
    sheet_name: Optional[str] = Field(default=None)
    record_tag: str = Field(default="record", description="XML record tag name")


SourceConfig = Union[APISourceConfig, RSSSourceConfig, WebSourceConfig, FileSourceConfig]


# ── Source CRUD models ─────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    """Request body for creating a new data source."""

    name: str = Field(..., min_length=1, max_length=256)
    source_type: Literal["api", "rss", "web", "file"] = Field(...)
    url: Optional[str] = Field(default=None, description="Base URL or feed URL")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-type-specific configuration",
    )
    legal_status: str = Field(
        default="unverified",
        description="Legal status: unverified | approved | restricted | rejected",
    )

    @field_validator("legal_status")
    @classmethod
    def validate_legal_status(cls, v: str) -> str:
        allowed = {"unverified", "approved", "restricted", "rejected"}
        if v not in allowed:
            raise ValueError(f"legal_status must be one of {allowed}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        if not re.match(r"^https?://", v, re.IGNORECASE):
            raise ValueError("URL must start with http:// or https://")
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class SourceUpdate(BaseModel):
    """Request body for updating a data source."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    config: Optional[Dict[str, Any]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    legal_status: Optional[str] = Field(default=None)

    @field_validator("legal_status")
    @classmethod
    def validate_legal_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"unverified", "approved", "restricted", "rejected"}
        if v not in allowed:
            raise ValueError(f"legal_status must be one of {allowed}")
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class SourceResponse(BaseModel):
    """API response model for a data source."""

    id: UUID
    name: str
    source_type: str
    url: Optional[str]
    config: Dict[str, Any]
    is_active: bool
    is_verified: bool
    legal_status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)
