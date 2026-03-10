"""Pydantic models for relationships."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    owns = "owns"
    communicates_with = "communicates_with"
    associated_with = "associated_with"
    located_at = "located_at"
    employs = "employs"
    funds = "funds"
    member_of = "member_of"
    alias_of = "alias_of"
    hosts = "hosts"
    registered_by = "registered_by"
    controls = "controls"
    similar_to = "similar_to"


class RelationshipCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_directed: bool = Field(default=True)


class RelationshipUpdate(BaseModel):
    relationship_type: Optional[RelationshipType] = None
    attributes: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class RelationshipResponse(BaseModel):
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    is_directed: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
