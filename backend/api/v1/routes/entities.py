"""
Entities router.

CRUD for intelligence entities with support for filtering, pagination,
alias management, and canonical deduplication.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Entity, User
from storage.database.postgres.queries import (
    count_records,
    create_record,
    delete_record,
    get_all,
    get_by_id,
    paginate,
    search_entities,
    update_record,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/entities")

VALID_ENTITY_TYPES = {
    "person", "organization", "location", "ip", "domain", "email",
    "phone", "url", "hash", "cryptocurrency", "vehicle", "document",
}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EntityCreate(BaseModel):
    entity_type: str = Field(..., description="One of the supported entity types")
    name: str = Field(..., min_length=1, max_length=512)
    aliases: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_canonical: bool = True


class EntityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    aliases: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_canonical: Optional[bool] = None


class EntityResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    name: str
    aliases: List[str]
    attributes: Dict[str, Any]
    confidence_score: float
    is_canonical: bool
    canonical_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, entity: Entity) -> "EntityResponse":
        return cls(
            id=entity.id,
            entity_type=entity.entity_type,
            name=entity.name,
            aliases=entity.aliases or [],
            attributes=entity.attributes or {},
            confidence_score=entity.confidence_score,
            is_canonical=entity.is_canonical,
            canonical_id=entity.canonical_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            created_by=entity.created_by,
        )


class EntityListResponse(BaseModel):
    items: List[EntityResponse]
    total: int
    page: int
    page_size: int
    pages: int


class MergeRequest(BaseModel):
    canonical_entity_id: uuid.UUID
    duplicate_entity_ids: List[uuid.UUID] = Field(..., min_length=1)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    body: EntityCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EntityResponse:
    """Create a new intelligence entity."""
    if body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity_type. Must be one of: {sorted(VALID_ENTITY_TYPES)}",
        )
    entity = await create_record(
        session,
        Entity,
        {
            "entity_type": body.entity_type,
            "name": body.name,
            "aliases": body.aliases,
            "attributes": body.attributes,
            "confidence_score": body.confidence_score,
            "is_canonical": body.is_canonical,
            "created_by": current_user.id,
        },
    )
    # Sync to Neo4j asynchronously (best-effort)
    try:
        from storage.database.graph.graph_sync import GraphSyncService
        await GraphSyncService().sync_entity(entity)
    except Exception:
        pass
    return EntityResponse.from_orm_model(entity)


@router.get("", response_model=EntityListResponse)
async def list_entities(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    entity_type: Optional[str] = None,
    is_canonical: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EntityListResponse:
    """List entities with optional type filter and pagination."""
    filters: Dict[str, Any] = {}
    if entity_type:
        if entity_type not in VALID_ENTITY_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid entity_type: {entity_type}")
        filters["entity_type"] = entity_type
    if is_canonical is not None:
        filters["is_canonical"] = is_canonical

    result = await paginate(session, Entity, page=page, page_size=page_size, filters=filters)
    return EntityListResponse(
        items=[EntityResponse.from_orm_model(e) for e in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.get("/search", response_model=List[EntityResponse])
async def search(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[EntityResponse]:
    """Search entities by name or alias (case-insensitive substring match)."""
    entities = await search_entities(
        session, search_term=q, entity_type=entity_type, skip=skip, limit=limit
    )
    return [EntityResponse.from_orm_model(e) for e in entities]


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EntityResponse:
    """Retrieve an entity by ID."""
    entity = await get_by_id(session, Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityResponse.from_orm_model(entity)


@router.patch("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: uuid.UUID,
    body: EntityUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EntityResponse:
    """Partially update an entity."""
    entity = await get_by_id(session, Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        return EntityResponse.from_orm_model(entity)

    updated = await update_record(session, Entity, entity_id, update_data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found after update")
    try:
        from storage.database.graph.graph_sync import GraphSyncService
        await GraphSyncService().sync_entity(updated)
    except Exception:
        pass
    return EntityResponse.from_orm_model(updated)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete an entity and remove it from the graph database."""
    deleted = await delete_record(session, Entity, entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    try:
        from storage.database.graph.graph_sync import GraphSyncService
        await GraphSyncService().sync_entity_deletion(entity_id)
    except Exception:
        pass


@router.post("/merge", response_model=List[EntityResponse])
async def merge_entities(
    body: MergeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[EntityResponse]:
    """
    Mark duplicate entities as non-canonical and point them at a canonical record.

    The canonical entity retains all data; duplicates are marked ``is_canonical=False``
    and have their ``canonical_id`` set to the canonical entity.
    """
    canonical = await get_by_id(session, Entity, body.canonical_entity_id)
    if canonical is None:
        raise HTTPException(status_code=404, detail="Canonical entity not found")

    updated = [canonical]
    for dup_id in body.duplicate_entity_ids:
        if dup_id == body.canonical_entity_id:
            continue
        dup = await update_record(
            session,
            Entity,
            dup_id,
            {"is_canonical": False, "canonical_id": body.canonical_entity_id},
        )
        if dup:
            updated.append(dup)

    return [EntityResponse.from_orm_model(e) for e in updated]
