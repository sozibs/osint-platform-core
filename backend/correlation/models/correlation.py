"""Pydantic models for correlation results and analysis."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Result from a single analyzer."""

    score: float = Field(ge=0.0, le=1.0, description="Correlation score between 0 and 1")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting the score")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed analysis data")
    analyzer_name: str = Field(description="Name of the analyzer that produced this result")


class CorrelationResult(BaseModel):
    """Result of correlating two entities."""

    entity1_id: UUID
    entity2_id: UUID
    correlation_score: float = Field(ge=0.0, le=1.0)
    correlation_type: str = Field(description="Type of correlation detected")
    evidence: List[str] = Field(default_factory=list)
    suggested_relationship: Optional[str] = Field(
        default=None,
        description="Suggested relationship type if score is high enough",
    )
    confidence: str = Field(
        description="Confidence level: speculative, possible, probable, confirmed"
    )
    analyzer_results: Dict[str, AnalysisResult] = Field(
        default_factory=dict,
        description="Per-analyzer breakdown",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Pattern(BaseModel):
    """A detected pattern across multiple entities."""

    pattern_type: str = Field(description="Type of pattern, e.g. subnet, domain_group")
    entities: List[UUID] = Field(default_factory=list, description="Entity IDs in pattern")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    description: str = Field(description="Human-readable description of the pattern")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class CaseAnalysisResult(BaseModel):
    """Full analysis result for a case."""

    case_id: UUID
    correlations: List[CorrelationResult] = Field(default_factory=list)
    patterns: List[Pattern] = Field(default_factory=list)
    suggested_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_time: float = Field(description="Analysis duration in seconds")
    entity_count: int = Field(default=0)
    analyzed_pairs: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
