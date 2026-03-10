"""
Pydantic request schemas for all OSINT Platform API v1 endpoints.

All schemas use strict validation to reject unexpected fields and enforce
business rules at the boundary layer, before any business logic runs.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VALID_ENTITY_TYPES = frozenset(
    {
        "person",
        "organization",
        "location",
        "ip",
        "domain",
        "email",
        "phone",
        "url",
        "hash",
        "cryptocurrency",
        "vehicle",
        "document",
    }
)

_VALID_CASE_STATUSES = frozenset({"open", "closed", "archived"})
_VALID_CASE_PRIORITIES = frozenset({"low", "medium", "high", "critical"})
_VALID_SORT_ORDERS = frozenset({"asc", "desc"})
_VALID_EXPORT_FORMATS = frozenset({"csv", "json", "pdf", "xlsx"})
_VALID_SOURCE_TYPES = frozenset({"api", "rss", "web", "file"})


class PaginationParams(BaseModel):
    """Reusable pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


# ---------------------------------------------------------------------------
# Entity schemas
# ---------------------------------------------------------------------------


class EntityCreate(BaseModel):
    """Create a new intelligence entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    entity_type: str = Field(..., description="One of the supported entity types")
    name: str = Field(..., min_length=1, max_length=512)
    aliases: List[str] = Field(default_factory=list, max_length=50)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("entity_type")
    @classmethod
    def _check_entity_type(cls, v: str) -> str:
        if v.lower() not in _VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type {v!r}. Must be one of: {sorted(_VALID_ENTITY_TYPES)}"
            )
        return v.lower()

    @field_validator("aliases")
    @classmethod
    def _check_aliases(cls, v: List[str]) -> List[str]:
        return [a.strip() for a in v if a.strip()]


class EntityUpdate(BaseModel):
    """Partially update an existing entity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    aliases: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_canonical: Optional[bool] = None


# ---------------------------------------------------------------------------
# Relationship schemas
# ---------------------------------------------------------------------------


class RelationshipCreate(BaseModel):
    """Create a directed or undirected relationship between two entities."""

    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str = Field(..., min_length=1, max_length=128)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_directed: bool = True
    source_id: Optional[UUID] = None

    @field_validator("relationship_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        return v.lower().replace(" ", "_")


class RelationshipUpdate(BaseModel):
    """Partially update an existing relationship."""

    relationship_type: Optional[str] = Field(default=None, min_length=1, max_length=128)
    attributes: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_directed: Optional[bool] = None


class BulkRelationshipCreate(BaseModel):
    """Create multiple relationships in a single request."""

    relationships: List[RelationshipCreate] = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Case schemas
# ---------------------------------------------------------------------------


class CaseCreate(BaseModel):
    """Create a new investigation case."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=8192)
    status: str = Field(default="open")
    priority: str = Field(default="medium")
    tags: List[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in _VALID_CASE_STATUSES:
            raise ValueError(f"status must be one of: {sorted(_VALID_CASE_STATUSES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: str) -> str:
        if v not in _VALID_CASE_PRIORITIES:
            raise ValueError(f"priority must be one of: {sorted(_VALID_CASE_PRIORITIES)}")
        return v


class CaseUpdate(BaseModel):
    """Partially update a case."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=8192)
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    assigned_to: Optional[UUID] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_CASE_STATUSES:
            raise ValueError(f"status must be one of: {sorted(_VALID_CASE_STATUSES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_CASE_PRIORITIES:
            raise ValueError(f"priority must be one of: {sorted(_VALID_CASE_PRIORITIES)}")
        return v


class CaseEntityAdd(BaseModel):
    """Add an entity to a case with optional notes."""

    entity_id: UUID
    notes: Optional[str] = Field(default=None, max_length=2048)


# ---------------------------------------------------------------------------
# Ingestion schemas
# ---------------------------------------------------------------------------


class IngestFileRequest(BaseModel):
    """Metadata accompanying a file ingestion request (sent as form fields)."""

    source_name: str = Field(..., min_length=1, max_length=256)
    tags: List[str] = Field(default_factory=list)
    mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Column-to-field mapping for CSV/XLSX files",
    )


class IngestUrlRequest(BaseModel):
    """Configure a URL-based ingestion source."""

    url: str = Field(..., min_length=1, max_length=2048)
    source_type: str = Field(default="web")
    config: Dict[str, Any] = Field(default_factory=dict)
    schedule: Optional[str] = Field(
        default=None,
        description="Cron expression for recurring ingestion, e.g. '0 */6 * * *'",
    )

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, v: str) -> str:
        if v not in _VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of: {sorted(_VALID_SOURCE_TYPES)}")
        return v


class IngestApiRequest(BaseModel):
    """Configure an API data source."""

    name: str = Field(..., min_length=1, max_length=256)
    url: str = Field(..., min_length=1, max_length=2048)
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="API-specific config (auth headers, params, pagination strategy, etc.)",
    )
    schedule: Optional[str] = Field(default=None)


class IngestRssRequest(BaseModel):
    """Configure an RSS/Atom feed source."""

    name: str = Field(..., min_length=1, max_length=256)
    url: str = Field(..., min_length=1, max_length=2048)
    schedule: Optional[str] = Field(default=None, description="Cron expression")


# ---------------------------------------------------------------------------
# Search schemas
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Simple search request."""

    query: str = Field(..., min_length=1, max_length=512)
    entity_types: List[str] = Field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AdvancedSearchFilter(BaseModel):
    """A single filter clause for advanced search."""

    field: str = Field(..., min_length=1, max_length=64)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"] = "eq"
    value: Any


class AdvancedSearchRequest(BaseModel):
    """Advanced search with structured filter DSL."""

    filters: List[AdvancedSearchFilter] = Field(default_factory=list)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("sort_order")
    @classmethod
    def _check_sort_order(cls, v: str) -> str:
        if v not in _VALID_SORT_ORDERS:
            raise ValueError(f"sort_order must be one of: {sorted(_VALID_SORT_ORDERS)}")
        return v


# ---------------------------------------------------------------------------
# Export schemas
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    """Request to export a set of entities."""

    format: str = Field(default="json")
    entity_ids: List[UUID] = Field(default_factory=list, max_length=10_000)
    include_relationships: bool = True

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: str) -> str:
        if v not in _VALID_EXPORT_FORMATS:
            raise ValueError(
                f"format must be one of: {sorted(_VALID_EXPORT_FORMATS)}"
            )
        return v


class CaseExportRequest(BaseModel):
    """Request to export a complete case package."""

    format: str = Field(default="json")
    include_relationships: bool = True
    include_sources: bool = True
    include_timeline: bool = True

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: str) -> str:
        if v not in _VALID_EXPORT_FORMATS:
            raise ValueError(f"format must be one of: {sorted(_VALID_EXPORT_FORMATS)}")
        return v


class GraphExportRequest(BaseModel):
    """Request to export a graph in a machine-readable format."""

    format: Literal["json", "graphml", "gexf"] = "json"
    entity_ids: List[UUID] = Field(
        default_factory=list,
        description="If empty, exports the entire graph (up to size limits)",
    )
    max_nodes: int = Field(default=5_000, ge=1, le=50_000)


class TimelineExportRequest(BaseModel):
    """Request to export a chronological timeline."""

    format: Literal["json", "csv", "pdf"] = "json"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    entity_ids: List[UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Graph schemas
# ---------------------------------------------------------------------------


class GraphSubgraphRequest(BaseModel):
    """Request for a subgraph centred on a specific entity."""

    entity_id: UUID
    depth: int = Field(default=2, ge=1, le=5)
    max_nodes: int = Field(default=200, ge=1, le=2_000)
