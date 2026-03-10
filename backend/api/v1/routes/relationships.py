"""
Relationships router.

CRUD for directed and undirected edges between intelligence entities.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Entity, Relationship, User
from storage.database.postgres.queries import (
    create_record,
    delete_record,
    get_by_id,
    get_entity_relationships,
    paginate,
    update_record,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/relationships")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RelationshipCreate(BaseModel):
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str = Field(..., min_length=1, max_length=128)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_directed: bool = True
    source_id: Optional[uuid.UUID] = None


class RelationshipUpdate(BaseModel):
    relationship_type: Optional[str] = Field(default=None, max_length=128)
    attributes: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_directed: Optional[bool] = None


class RelationshipResponse(BaseModel):
    id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    attributes: Dict[str, Any]
    confidence_score: float
    is_directed: bool
    source_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, r: Relationship) -> "RelationshipResponse":
        return cls(
            id=r.id,
            source_entity_id=r.source_entity_id,
            target_entity_id=r.target_entity_id,
            relationship_type=r.relationship_type,
            attributes=r.attributes or {},
            confidence_score=r.confidence_score,
            is_directed=r.is_directed,
            source_id=r.source_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


class RelationshipListResponse(BaseModel):
    items: List[RelationshipResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    body: RelationshipCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RelationshipResponse:
    """Create a relationship between two entities."""
    # Validate both entities exist
    src = await get_by_id(session, Entity, body.source_entity_id)
    tgt = await get_by_id(session, Entity, body.target_entity_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Source entity not found")
    if tgt is None:
        raise HTTPException(status_code=404, detail="Target entity not found")

    rel = await create_record(
        session,
        Relationship,
        {
            "source_entity_id": body.source_entity_id,
            "target_entity_id": body.target_entity_id,
            "relationship_type": body.relationship_type,
            "attributes": body.attributes,
            "confidence_score": body.confidence_score,
            "is_directed": body.is_directed,
            "source_id": body.source_id,
        },
    )
    try:
        from storage.database.graph.graph_sync import GraphSyncService
        await GraphSyncService().sync_relationship(rel)
    except Exception:
        pass
    return RelationshipResponse.from_orm_model(rel)


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    relationship_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RelationshipListResponse:
    """List all relationships with optional type filter."""
    filters: Dict[str, Any] = {}
    if relationship_type:
        filters["relationship_type"] = relationship_type
    result = await paginate(
        session, Relationship, page=page, page_size=page_size, filters=filters
    )
    return RelationshipListResponse(
        items=[RelationshipResponse.from_orm_model(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.get("/entity/{entity_id}", response_model=List[RelationshipResponse])
async def get_entity_rels(
    entity_id: uuid.UUID,
    direction: str = Query(default="both", pattern="^(outgoing|incoming|both)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[RelationshipResponse]:
    """Return all relationships for a given entity."""
    entity = await get_by_id(session, Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    rels = await get_entity_relationships(session, entity_id, direction=direction)
    return [RelationshipResponse.from_orm_model(r) for r in rels]


@router.get("/{rel_id}", response_model=RelationshipResponse)
async def get_relationship(
    rel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RelationshipResponse:
    """Retrieve a relationship by ID."""
    rel = await get_by_id(session, Relationship, rel_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return RelationshipResponse.from_orm_model(rel)


@router.patch("/{rel_id}", response_model=RelationshipResponse)
async def update_relationship(
    rel_id: uuid.UUID,
    body: RelationshipUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RelationshipResponse:
    """Partially update a relationship."""
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        rel = await get_by_id(session, Relationship, rel_id)
        if rel is None:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return RelationshipResponse.from_orm_model(rel)

    updated = await update_record(session, Relationship, rel_id, update_data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return RelationshipResponse.from_orm_model(updated)


@router.delete("/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    rel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a relationship."""
    deleted = await delete_record(session, Relationship, rel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")
