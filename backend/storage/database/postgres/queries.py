"""Common async query helpers for PostgreSQL database operations."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database.postgres import Base

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


async def get_by_id(session: AsyncSession, model: Type[T], id: UUID) -> Optional[T]:
    """Fetch a single record by its UUID primary key."""
    result = await session.execute(select(model).where(model.id == id))  # type: ignore[attr-defined]
    return result.scalar_one_or_none()


async def get_all(
    session: AsyncSession,
    model: Type[T],
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
) -> List[T]:
    """Fetch a paginated list of records with optional equality filters."""
    query = select(model)
    if filters:
        conditions = [
            getattr(model, k) == v
            for k, v in filters.items()
            if hasattr(model, k)
        ]
        if conditions:
            query = query.where(and_(*conditions))
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_record(session: AsyncSession, model: Type[T], data: Dict[str, Any]) -> T:
    """Insert a new record, flush to obtain the generated PK, and refresh."""
    instance = model(**data)
    session.add(instance)
    await session.flush()
    await session.refresh(instance)
    return instance


async def update_record(
    session: AsyncSession, model: Type[T], id: UUID, data: Dict[str, Any]
) -> Optional[T]:
    """Update a record by PK, return the updated instance or None if not found."""
    stmt = (
        update(model)  # type: ignore[arg-type]
        .where(model.id == id)  # type: ignore[attr-defined]
        .values(**data)
        .returning(model)  # type: ignore[call-overload]
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.scalar_one_or_none()


async def delete_record(session: AsyncSession, model: Type[T], id: UUID) -> bool:
    """Delete a record by PK. Returns True if a row was deleted."""
    stmt = delete(model).where(model.id == id)  # type: ignore[attr-defined]
    result = await session.execute(stmt)
    return result.rowcount > 0


async def count_records(
    session: AsyncSession,
    model: Type[T],
    filters: Optional[Dict[str, Any]] = None,
) -> int:
    """Count records in a table with optional equality filters."""
    query = select(func.count()).select_from(model)  # type: ignore[arg-type]
    if filters:
        conditions = [
            getattr(model, k) == v
            for k, v in filters.items()
            if hasattr(model, k)
        ]
        if conditions:
            query = query.where(and_(*conditions))
    result = await session.execute(query)
    return result.scalar_one()


async def search_entities(
    session: AsyncSession,
    search_term: str,
    entity_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Any]:
    """
    Full-text-style search across entity name and aliases.

    Uses PostgreSQL ILIKE for case-insensitive substring matching.
    For production deployments with large datasets, pair this with a
    GIN index on the ``aliases`` JSONB column and consider Elasticsearch.
    """
    from storage.database.postgres.models import Entity

    query = select(Entity).where(
        or_(
            Entity.name.ilike(f"%{search_term}%"),
            func.cast(Entity.aliases, text("text")).ilike(f"%{search_term}%"),
        )
    )
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_entity_relationships(
    session: AsyncSession,
    entity_id: UUID,
    direction: str = "both",
) -> List[Any]:
    """
    Retrieve relationships for a given entity.

    direction: "outgoing" | "incoming" | "both"
    """
    from storage.database.postgres.models import Relationship

    if direction == "outgoing":
        condition = Relationship.source_entity_id == entity_id
    elif direction == "incoming":
        condition = Relationship.target_entity_id == entity_id
    else:
        condition = or_(
            Relationship.source_entity_id == entity_id,
            Relationship.target_entity_id == entity_id,
        )

    query = select(Relationship).where(condition)
    result = await session.execute(query)
    return list(result.scalars().all())


async def paginate(
    session: AsyncSession,
    model: Type[T],
    page: int = 1,
    page_size: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a pagination envelope: items, total count, page metadata.

    page is 1-indexed.
    """
    if page < 1:
        page = 1
    skip = (page - 1) * page_size
    total = await count_records(session, model, filters)
    items = await get_all(session, model, skip=skip, limit=page_size, filters=filters)
    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


async def bulk_create(
    session: AsyncSession, model: Type[T], data_list: List[Dict[str, Any]]
) -> List[T]:
    """Insert multiple records in a single flush."""
    instances = [model(**data) for data in data_list]
    session.add_all(instances)
    await session.flush()
    for instance in instances:
        await session.refresh(instance)
    return instances


async def exists_by_field(
    session: AsyncSession, model: Type[T], field: str, value: Any
) -> bool:
    """Check whether a record exists by an arbitrary field."""
    if not hasattr(model, field):
        return False
    query = select(func.count()).select_from(model).where(  # type: ignore[arg-type]
        getattr(model, field) == value
    )
    result = await session.execute(query)
    return (result.scalar_one() or 0) > 0
