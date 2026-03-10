"""Pydantic models for ingestion records, jobs, and processing results."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class IngestionJobStatus(str, Enum):
    """Lifecycle states for an ingestion job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Core record models ─────────────────────────────────────────────────────────

class IngestionRecord(BaseModel):
    """Represents a single raw + normalized ingestion record."""

    source_id: UUID
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    normalized_data: Optional[Dict[str, Any]] = Field(default=None)
    entity_type: Optional[str] = Field(default=None)
    status: str = Field(default="pending")
    error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(str_strip_whitespace=True)


class NormalizedRecord(BaseModel):
    """A record that has been normalized and is ready for entity creation."""

    entity_type: str = Field(..., description="Canonical entity type")
    name: str = Field(..., min_length=1, description="Primary identifier/name for the entity")
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Entity-type-specific structured attributes",
    )
    source_url: Optional[str] = Field(default=None)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProcessingResult(BaseModel):
    """Aggregated result returned by the ingestion processor."""

    total: int = Field(default=0, ge=0, description="Total records submitted")
    successful: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    entities_created: int = Field(default=0, ge=0)
    relationships_created: int = Field(default=0, ge=0)
    errors: List[str] = Field(default_factory=list)
    duration_ms: float = Field(default=0.0, ge=0.0)

    @property
    def success_rate(self) -> float:
        """Fraction of records processed successfully (0-1)."""
        if self.total == 0:
            return 1.0
        return self.successful / self.total


# ── Ingestion job models ───────────────────────────────────────────────────────

class IngestionJob(BaseModel):
    """Tracks the lifecycle and progress of a background ingestion job."""

    job_id: str = Field(..., description="Celery task UUID or unique job identifier")
    status: IngestionJobStatus = Field(default=IngestionJobStatus.PENDING)
    source_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Progress fraction (0-1)"
    )
    total_records: int = Field(default=0, ge=0)
    processed_records: int = Field(default=0, ge=0)
    entities_created: int = Field(default=0, ge=0)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None, description="Top-level error message if failed")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Final processing result dict"
    )

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    def update_progress(self, processed: int) -> None:
        """Update processed_records and recalculate progress fraction."""
        self.processed_records = processed
        if self.total_records > 0:
            self.progress = min(processed / self.total_records, 1.0)

    def mark_running(self) -> None:
        self.status = IngestionJobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def mark_completed(self, result: Dict[str, Any]) -> None:
        self.status = IngestionJobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 1.0
        self.result = result

    def mark_failed(self, error: str) -> None:
        self.status = IngestionJobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error

    def mark_cancelled(self) -> None:
        self.status = IngestionJobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
