"""
Search router.

Provides unified full-text and faceted search across entities, relationships,
cases, and sources.  Supports Elasticsearch when configured and falls back to
PostgreSQL ILIKE queries.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from config import settings
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Case, Entity, Relationship, Source, User
from storage.database.postgres.queries import search_entities

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SearchHit(BaseModel):
    resource_type: str
    id: str
    name: str
    entity_type: Optional[str] = None
    score: float = 1.0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: List[SearchHit]
    backend: str


class ElasticsearchQuery(BaseModel):
    query: str
    index: str = "entities"
    filters: Dict[str, Any] = Field(default_factory=dict)
    size: int = Field(default=20, ge=1, le=200)
    from_: int = Field(default=0, ge=0, alias="from")

    class Config:
        populate_by_name = True


# ── Elasticsearch helper ──────────────────────────────────────────────────────

async def _es_search(
    query: str,
    index: str,
    filters: Dict[str, Any],
    size: int,
    from_: int,
) -> List[Dict[str, Any]]:
    """Query Elasticsearch and return raw hits."""
    if not settings.ES_URL:
        return []
    try:
        from elasticsearch import AsyncElasticsearch

        async with AsyncElasticsearch(settings.ES_URL) as es:
            must_clauses: List[Dict[str, Any]] = [
                {"multi_match": {"query": query, "fields": ["name^3", "aliases^2", "*"]}}
            ]
            for field, value in filters.items():
                must_clauses.append({"term": {field: value}})

            body = {
                "query": {"bool": {"must": must_clauses}},
                "size": size,
                "from": from_,
            }
            response = await es.search(index=index, body=body)
            return response["hits"]["hits"]
    except Exception as exc:
        logger.warning("Elasticsearch search failed: %s", exc)
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=SearchResponse)
async def universal_search(
    q: str = Query(..., min_length=1, description="Search query string"),
    entity_type: Optional[str] = None,
    resource_type: Optional[str] = Query(
        default=None,
        description="Filter by resource type: entity, case, source, relationship",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SearchResponse:
    """
    Universal search across all OSINT platform resources.

    Queries Elasticsearch when available; falls back to PostgreSQL.
    """
    hits: List[SearchHit] = []
    backend = "postgresql"

    # ── Try Elasticsearch first ────────────────────────────────────────────
    if settings.ES_URL and (resource_type is None or resource_type == "entity"):
        filters: Dict[str, Any] = {}
        if entity_type:
            filters["entity_type"] = entity_type
        es_hits = await _es_search(
            query=q, index="entities", filters=filters, size=limit, from_=skip
        )
        if es_hits:
            backend = "elasticsearch"
            for hit in es_hits:
                src = hit.get("_source", {})
                hits.append(
                    SearchHit(
                        resource_type="entity",
                        id=hit["_id"],
                        name=src.get("name", ""),
                        entity_type=src.get("entity_type"),
                        score=hit.get("_score", 1.0),
                        attributes=src,
                    )
                )

    # ── PostgreSQL fallback / additional resource types ────────────────────
    if not hits or resource_type in {None, "entity"}:
        entities = await search_entities(
            session, search_term=q, entity_type=entity_type, skip=skip, limit=limit
        )
        entity_ids_seen = {h.id for h in hits}
        for entity in entities:
            eid = str(entity.id)
            if eid not in entity_ids_seen:
                hits.append(
                    SearchHit(
                        resource_type="entity",
                        id=eid,
                        name=entity.name,
                        entity_type=entity.entity_type,
                        score=entity.confidence_score,
                        attributes=entity.attributes or {},
                    )
                )

    if resource_type in {None, "case"}:
        case_result = await session.execute(
            select(Case).where(Case.name.ilike(f"%{q}%")).limit(limit)
        )
        for case in case_result.scalars().all():
            hits.append(
                SearchHit(
                    resource_type="case",
                    id=str(case.id),
                    name=case.name,
                    score=1.0,
                    attributes={"status": case.status, "priority": case.priority},
                )
            )

    if resource_type in {None, "source"}:
        src_result = await session.execute(
            select(Source).where(Source.name.ilike(f"%{q}%")).limit(limit)
        )
        for src in src_result.scalars().all():
            hits.append(
                SearchHit(
                    resource_type="source",
                    id=str(src.id),
                    name=src.name,
                    score=1.0,
                    attributes={"source_type": src.source_type},
                )
            )

    hits = hits[:limit]
    return SearchResponse(query=q, total=len(hits), hits=hits, backend=backend)


@router.post("/elasticsearch", response_model=SearchResponse)
async def elasticsearch_query(
    body: ElasticsearchQuery,
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """
    Execute a raw Elasticsearch query.

    Returns HTTP 503 if Elasticsearch is not configured.
    """
    from fastapi import HTTPException

    if not settings.ES_URL:
        raise HTTPException(
            status_code=503,
            detail="Elasticsearch is not configured (set ES_URL environment variable)",
        )
    es_hits = await _es_search(
        query=body.query,
        index=body.index,
        filters=body.filters,
        size=body.size,
        from_=body.from_,
    )
    hits = [
        SearchHit(
            resource_type=body.index.rstrip("s"),
            id=h["_id"],
            name=h.get("_source", {}).get("name", ""),
            score=h.get("_score", 1.0),
            attributes=h.get("_source", {}),
        )
        for h in es_hits
    ]
    return SearchResponse(
        query=body.query, total=len(hits), hits=hits, backend="elasticsearch"
    )


@router.get("/suggest", response_model=List[str])
async def autocomplete_suggest(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[str]:
    """Return autocomplete name suggestions for the given prefix."""
    query = select(Entity.name).where(Entity.name.ilike(f"{q}%"))
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())
