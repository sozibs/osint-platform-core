"""
Cases router.

Investigation case management: create, update, close, archive cases and
associate intelligence entities with them.
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
from storage.database.postgres.models import Case, CaseEntity, Entity, User
from storage.database.postgres.queries import (
    create_record,
    delete_record,
    get_all,
    get_by_id,
    paginate,
    update_record,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases")

VALID_STATUSES = {"open", "closed", "archived"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    status: str = Field(default="open")
    priority: str = Field(default="medium")
    tags: List[str] = Field(default_factory=list)
    assigned_to: Optional[uuid.UUID] = None


class CaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    assigned_to: Optional[uuid.UUID] = None


class CaseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    priority: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID
    assigned_to: Optional[uuid.UUID]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, case: Case) -> "CaseResponse":
        return cls(
            id=case.id,
            name=case.name,
            description=case.description,
            status=case.status,
            priority=case.priority,
            tags=case.tags or [],
            created_at=case.created_at,
            updated_at=case.updated_at,
            created_by=case.created_by,
            assigned_to=case.assigned_to,
        )


class CaseListResponse(BaseModel):
    items: List[CaseResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AddEntityRequest(BaseModel):
    entity_id: uuid.UUID
    notes: Optional[str] = None


class CaseEntityResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    entity_id: uuid.UUID
    added_at: datetime
    added_by: uuid.UUID
    notes: Optional[str]
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CaseResponse:
    """Create a new investigation case."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUSES}")
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {VALID_PRIORITIES}")

    case = await create_record(
        session,
        Case,
        {
            "name": body.name,
            "description": body.description,
            "status": body.status,
            "priority": body.priority,
            "tags": body.tags,
            "created_by": current_user.id,
            "assigned_to": body.assigned_to,
        },
    )
    return CaseResponse.from_orm_model(case)


@router.get("", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CaseListResponse:
    """List investigation cases with optional filters."""
    filters: Dict[str, Any] = {}
    if status_filter:
        filters["status"] = status_filter
    if priority:
        filters["priority"] = priority
    result = await paginate(session, Case, page=page, page_size=page_size, filters=filters)
    return CaseListResponse(
        items=[CaseResponse.from_orm_model(c) for c in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CaseResponse:
    """Retrieve a case by ID."""
    case = await get_by_id(session, Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse.from_orm_model(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    body: CaseUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CaseResponse:
    """Partially update a case."""
    update_data = body.model_dump(exclude_none=True)
    if "status" in update_data and update_data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUSES}")
    if "priority" in update_data and update_data["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {VALID_PRIORITIES}")
    if not update_data:
        case = await get_by_id(session, Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return CaseResponse.from_orm_model(case)

    updated = await update_record(session, Case, case_id, update_data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse.from_orm_model(updated)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a case and all its entity associations."""
    deleted = await delete_record(session, Case, case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")


# ── Case entity management ────────────────────────────────────────────────────

@router.post("/{case_id}/entities", response_model=CaseEntityResponse, status_code=201)
async def add_entity_to_case(
    case_id: uuid.UUID,
    body: AddEntityRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CaseEntityResponse:
    """Associate an entity with a case."""
    case = await get_by_id(session, Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    entity = await get_by_id(session, Entity, body.entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Check for duplicate
    existing = await get_all(
        session, CaseEntity, filters={"case_id": case_id, "entity_id": body.entity_id}
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Entity is already associated with this case"
        )

    ce = await create_record(
        session,
        CaseEntity,
        {
            "case_id": case_id,
            "entity_id": body.entity_id,
            "added_by": current_user.id,
            "notes": body.notes,
        },
    )
    return CaseEntityResponse(
        id=ce.id,
        case_id=ce.case_id,
        entity_id=ce.entity_id,
        added_at=ce.added_at,
        added_by=ce.added_by,
        notes=ce.notes,
        entity_name=entity.name,
        entity_type=entity.entity_type,
    )


@router.get("/{case_id}/entities", response_model=List[CaseEntityResponse])
async def list_case_entities(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[CaseEntityResponse]:
    """List all entities associated with a case."""
    case = await get_by_id(session, Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case_entities = await get_all(session, CaseEntity, filters={"case_id": case_id})
    result = []
    for ce in case_entities:
        entity = await get_by_id(session, Entity, ce.entity_id)
        result.append(
            CaseEntityResponse(
                id=ce.id,
                case_id=ce.case_id,
                entity_id=ce.entity_id,
                added_at=ce.added_at,
                added_by=ce.added_by,
                notes=ce.notes,
                entity_name=entity.name if entity else None,
                entity_type=entity.entity_type if entity else None,
            )
        )
    return result


@router.delete("/{case_id}/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_entity_from_case(
    case_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Remove an entity association from a case."""
    case_entities = await get_all(
        session, CaseEntity, filters={"case_id": case_id, "entity_id": entity_id}
    )
    if not case_entities:
        raise HTTPException(status_code=404, detail="Case-entity association not found")
    await delete_record(session, CaseEntity, case_entities[0].id)
