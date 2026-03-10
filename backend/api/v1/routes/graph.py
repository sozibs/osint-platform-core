"""
Graph analysis router.

Provides graph traversal, shortest-path, neighbourhood, and community-
detection queries powered by Neo4j (when configured) and NetworkX for
in-memory analytics.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from storage.database.graph.neo4j_adapter import get_neo4j
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Entity, Relationship, User
from storage.database.postgres.queries import get_by_id, get_entity_relationships

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: str
    name: str
    confidence_score: float
    is_canonical: bool
    attributes: Dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence_score: float
    is_directed: bool
    attributes: Dict[str, Any]


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    node_count: int
    edge_count: int


class ShortestPathResponse(BaseModel):
    path: List[Dict[str, Any]]
    length: int
    found: bool


class NeighbourhoodResponse(BaseModel):
    centre_entity_id: str
    depth: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class CommunityResponse(BaseModel):
    communities: List[List[str]]
    total_communities: int
    algorithm: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _build_nx_graph(session: AsyncSession) -> nx.DiGraph:
    """Load all entities and relationships into a NetworkX DiGraph."""
    g: nx.DiGraph = nx.DiGraph()

    entity_result = await session.execute(select(Entity))
    for entity in entity_result.scalars().all():
        g.add_node(
            str(entity.id),
            name=entity.name,
            entity_type=entity.entity_type,
            confidence_score=entity.confidence_score,
        )

    rel_result = await session.execute(select(Relationship))
    for rel in rel_result.scalars().all():
        g.add_edge(
            str(rel.source_entity_id),
            str(rel.target_entity_id),
            id=str(rel.id),
            relationship_type=rel.relationship_type,
            confidence_score=rel.confidence_score,
            is_directed=rel.is_directed,
        )
    return g


def _entity_to_node(entity: Entity) -> GraphNode:
    return GraphNode(
        id=str(entity.id),
        label=entity.name,
        entity_type=entity.entity_type,
        name=entity.name,
        confidence_score=entity.confidence_score,
        is_canonical=entity.is_canonical,
        attributes=entity.attributes or {},
    )


def _rel_to_edge(rel: Relationship) -> GraphEdge:
    return GraphEdge(
        id=str(rel.id),
        source=str(rel.source_entity_id),
        target=str(rel.target_entity_id),
        relationship_type=rel.relationship_type,
        confidence_score=rel.confidence_score,
        is_directed=rel.is_directed,
        attributes=rel.attributes or {},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/full", response_model=GraphResponse)
async def full_graph(
    limit: int = Query(default=500, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GraphResponse:
    """
    Return the full entity-relationship graph (up to *limit* entities).

    For large datasets use the neighbourhood endpoint to fetch subgraphs.
    """
    entity_result = await session.execute(select(Entity).limit(limit))
    entities = list(entity_result.scalars().all())
    entity_ids = {str(e.id) for e in entities}

    rel_result = await session.execute(select(Relationship))
    rels = [
        r for r in rel_result.scalars().all()
        if str(r.source_entity_id) in entity_ids
        and str(r.target_entity_id) in entity_ids
    ]

    nodes = [_entity_to_node(e) for e in entities]
    edges = [_rel_to_edge(r) for r in rels]
    return GraphResponse(
        nodes=nodes, edges=edges, node_count=len(nodes), edge_count=len(edges)
    )


@router.get("/neighbourhood/{entity_id}", response_model=NeighbourhoodResponse)
async def neighbourhood(
    entity_id: uuid.UUID,
    depth: int = Query(default=2, ge=1, le=5),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> NeighbourhoodResponse:
    """
    Return the ego-graph centred on *entity_id* up to *depth* hops.
    """
    centre = await get_by_id(session, Entity, entity_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    # BFS across PostgreSQL relationships
    visited_entities: Dict[str, Entity] = {str(centre.id): centre}
    visited_rels: Dict[str, Relationship] = {}
    frontier: List[uuid.UUID] = [entity_id]

    for _ in range(depth):
        next_frontier: List[uuid.UUID] = []
        for eid in frontier:
            rels = await get_entity_relationships(session, eid, direction="both")
            for rel in rels:
                rel_key = str(rel.id)
                if rel_key not in visited_rels:
                    visited_rels[rel_key] = rel
                for neighbour_id in (rel.source_entity_id, rel.target_entity_id):
                    nid = str(neighbour_id)
                    if nid not in visited_entities:
                        entity = await get_by_id(session, Entity, neighbour_id)
                        if entity:
                            visited_entities[nid] = entity
                            next_frontier.append(neighbour_id)
        frontier = next_frontier
        if not frontier:
            break

    nodes = [_entity_to_node(e) for e in visited_entities.values()]
    edges = [_rel_to_edge(r) for r in visited_rels.values()]

    return NeighbourhoodResponse(
        centre_entity_id=str(entity_id),
        depth=depth,
        nodes=nodes,
        edges=edges,
    )


@router.get("/shortest-path", response_model=ShortestPathResponse)
async def shortest_path(
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    use_neo4j: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ShortestPathResponse:
    """
    Compute the shortest path between two entities.

    Uses Neo4j when ``use_neo4j=true`` and Neo4j is configured; falls back
    to in-memory NetworkX computation.
    """
    neo4j = get_neo4j()
    if use_neo4j and neo4j is not None:
        path_nodes = await neo4j.get_shortest_path(str(from_id), str(to_id))
        if path_nodes:
            return ShortestPathResponse(path=path_nodes, length=len(path_nodes) - 1, found=True)
        return ShortestPathResponse(path=[], length=0, found=False)

    # NetworkX fallback
    g = await _build_nx_graph(session)
    from_key = str(from_id)
    to_key = str(to_id)
    if from_key not in g or to_key not in g:
        return ShortestPathResponse(path=[], length=0, found=False)
    try:
        path_ids = nx.shortest_path(g, from_key, to_key)
        path_data = [{"id": node_id, **g.nodes[node_id]} for node_id in path_ids]
        return ShortestPathResponse(path=path_data, length=len(path_ids) - 1, found=True)
    except nx.NetworkXNoPath:
        return ShortestPathResponse(path=[], length=0, found=False)
    except nx.NodeNotFound:
        return ShortestPathResponse(path=[], length=0, found=False)


@router.get("/communities", response_model=CommunityResponse)
async def detect_communities(
    algorithm: str = Query(default="louvain", pattern="^(louvain|label_propagation)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CommunityResponse:
    """
    Detect communities in the entity graph using NetworkX.

    Algorithms: ``louvain`` (default), ``label_propagation``.
    """
    g = await _build_nx_graph(session)
    undirected = g.to_undirected()

    if undirected.number_of_nodes() == 0:
        return CommunityResponse(communities=[], total_communities=0, algorithm=algorithm)

    if algorithm == "louvain":
        try:
            communities_gen = nx.community.louvain_communities(undirected, seed=42)
            communities = [list(c) for c in communities_gen]
        except Exception:
            # Louvain may not be available in all nx builds; fall back
            communities_gen = nx.community.label_propagation_communities(undirected)
            communities = [list(c) for c in communities_gen]
            algorithm = "label_propagation"
    else:
        communities_gen = nx.community.label_propagation_communities(undirected)
        communities = [list(c) for c in communities_gen]

    return CommunityResponse(
        communities=communities,
        total_communities=len(communities),
        algorithm=algorithm,
    )


@router.post("/sync-neo4j", response_model=Dict[str, Any])
async def sync_to_neo4j(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Trigger a full synchronisation of all entities and relationships to Neo4j."""
    neo4j = get_neo4j()
    if neo4j is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j is not configured (set NEO4J_URL environment variable)",
        )
    from storage.database.graph.graph_sync import GraphSyncService

    service = GraphSyncService(neo4j)
    await neo4j.connect()
    try:
        summary = await service.full_sync(session)
    finally:
        await neo4j.close()

    return summary
