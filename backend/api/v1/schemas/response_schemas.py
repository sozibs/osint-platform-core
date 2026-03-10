"""
Pydantic response schemas for all OSINT Platform API v1 endpoints.

All ORM-backed schemas use ``model_config = ConfigDict(from_attributes=True)``
so that SQLAlchemy models can be passed to ``model_validate`` directly.

Generic types (``PaginatedResponse[T]``) use the Pydantic v2 generic model
pattern.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic / shared
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Wrapper for any paginated list response.

    Usage::

        return PaginatedResponse[EntityResponse](
            items=[...],
            total=100,
            page=1,
            page_size=20,
            pages=5,
        )
    """

    items: List[T]
    total: int = Field(..., ge=0, description="Total number of matching records")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0, description="Total number of pages")


class ErrorResponse(BaseModel):
    """Structured error payload returned on 4xx / 5xx responses."""

    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utcnow)


class HealthResponse(BaseModel):
    """Response from the ``/health`` endpoint."""

    status: str
    version: str
    timestamp: datetime = Field(default_factory=_utcnow)
    services: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of service name to status string",
    )


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class EntityResponse(BaseModel):
    """Serialized intelligence entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    is_canonical: bool
    canonical_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------


class RelationshipResponse(BaseModel):
    """Serialized relationship between two entities."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    is_directed: bool
    source_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------


class CaseResponse(BaseModel):
    """Serialized investigation case."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    status: str
    priority: str
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    entity_count: int = 0


class CaseEntityResponse(BaseModel):
    """An entity membership record within a case."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    entity_id: UUID
    added_at: datetime
    added_by: Optional[UUID] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class SourceResponse(BaseModel):
    """Serialized data source."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    url: Optional[str] = None
    is_active: bool
    is_verified: bool
    legal_status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchHitResponse(BaseModel):
    """A single hit in a search result set."""

    resource_type: str
    id: str
    name: str
    entity_type: Optional[str] = None
    score: float = 1.0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Unified search result set."""

    entities: List[EntityResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    query_time_ms: float = Field(default=0.0, description="Server-side query time in ms")


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


class GraphNodeResponse(BaseModel):
    """A node in a graph response."""

    id: str
    label: str
    entity_type: str
    name: str
    confidence_score: float
    is_canonical: bool
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphEdgeResponse(BaseModel):
    """An edge in a graph response."""

    id: str
    source: str
    target: str
    relationship_type: str
    confidence_score: float
    is_directed: bool
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """Complete graph payload with nodes, edges, and metadata."""

    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (e.g. algorithm used, depth, centrality stats)",
    )


# ---------------------------------------------------------------------------
# Ingestion job
# ---------------------------------------------------------------------------


class IngestionJobResponse(BaseModel):
    """Status of an asynchronous ingestion job."""

    job_id: str
    status: str = Field(
        ...,
        description="One of: pending, running, completed, failed, cancelled",
    )
    source: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Percent complete")
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Export job
# ---------------------------------------------------------------------------


class ExportJobResponse(BaseModel):
    """Status (and download link) for an asynchronous export job."""

    job_id: str
    status: str = Field(
        ...,
        description="One of: pending, running, completed, failed",
    )
    format: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = Field(
        default=None,
        description="Pre-signed URL to download the export file (available when status=completed)",
    )
    error: Optional[str] = None
    file_size_bytes: Optional[int] = None
