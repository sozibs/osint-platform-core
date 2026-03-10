"""
Neo4j graph database adapter.

The driver is imported lazily; if the `neo4j` package is not installed or
NEO4J_URL is not configured the adapter degrades gracefully and every method
returns None / empty results rather than raising an exception.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Try to import the official Neo4j Python driver.
try:
    import neo4j
    from neo4j import AsyncGraphDatabase, AsyncDriver
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    logger.warning(
        "neo4j Python driver not installed; graph database features are disabled. "
        "Install with: pip install neo4j"
    )


class Neo4jAdapter:
    """
    Async wrapper around the official Neo4j Python driver.

    Usage::

        adapter = Neo4jAdapter(url, user, password)
        await adapter.connect()
        await adapter.create_node("Entity", {"id": str(entity_id), "name": "Alice"})
        await adapter.close()
    """

    def __init__(self, url: str, user: str, password: str) -> None:
        self._url = url
        self._user = user
        self._password = password
        self._driver: Optional[Any] = None  # AsyncDriver

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the driver connection pool."""
        if not _NEO4J_AVAILABLE:
            logger.warning("Neo4j driver unavailable; skipping connect()")
            return
        if not self._url:
            logger.warning("NEO4J_URL not configured; skipping connect()")
            return
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._url,
                auth=(self._user, self._password),
                max_connection_pool_size=20,
            )
            await self._driver.verify_connectivity()
            logger.info("Neo4j connection established at %s", self._url)
        except Exception as exc:
            logger.error("Failed to connect to Neo4j: %s", exc)
            self._driver = None

    async def close(self) -> None:
        """Close the driver and release all connections."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    async def health_check(self) -> bool:
        """Return True if the database is reachable."""
        if self._driver is None:
            return False
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("Neo4j health check failed: %s", exc)
            return False

    # ── Node operations ───────────────────────────────────────────────────────

    async def create_node(
        self, label: str, properties: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create or merge a node with the given label and properties.

        Merge is keyed on the ``id`` property to ensure idempotency.
        """
        if self._driver is None:
            return None
        query = (
            f"MERGE (n:{label} {{id: $id}}) "
            "SET n += $props "
            "RETURN n"
        )
        node_id = str(properties.get("id", ""))
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query, id=node_id, props={k: str(v) for k, v in properties.items()}
                )
                record = await result.single()
                if record:
                    return dict(record["n"])
        except Exception as exc:
            logger.error("Neo4j create_node failed: %s", exc)
        return None

    async def find_node(
        self, label: str, property_key: str, property_value: Any
    ) -> Optional[Dict[str, Any]]:
        """Return the first node matching label + property, or None."""
        if self._driver is None:
            return None
        query = f"MATCH (n:{label} {{{property_key}: $value}}) RETURN n LIMIT 1"
        try:
            async with self._driver.session() as session:
                result = await session.run(query, value=str(property_value))
                record = await result.single()
                if record:
                    return dict(record["n"])
        except Exception as exc:
            logger.error("Neo4j find_node failed: %s", exc)
        return None

    # ── Relationship operations ───────────────────────────────────────────────

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create or merge a directed relationship between two nodes identified by
        their ``id`` property.  Both nodes must already exist.
        """
        if self._driver is None:
            return None
        props = {k: str(v) for k, v in (properties or {}).items()}
        query = (
            "MATCH (a {id: $from_id}), (b {id: $to_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $props "
            "RETURN r"
        )
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query, from_id=str(from_id), to_id=str(to_id), props=props
                )
                record = await result.single()
                if record:
                    return dict(record["r"])
        except Exception as exc:
            logger.error("Neo4j create_relationship failed: %s", exc)
        return None

    # ── Path / query operations ───────────────────────────────────────────────

    async def get_shortest_path(
        self, from_id: str, to_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Return the shortest path between two nodes (by id property) as a list
        of node property dicts, or None if no path exists.
        """
        if self._driver is None:
            return None
        query = (
            "MATCH (a {id: $from_id}), (b {id: $to_id}), "
            "p = shortestPath((a)-[*]-(b)) "
            "RETURN [n IN nodes(p) | properties(n)] AS path_nodes"
        )
        try:
            async with self._driver.session() as session:
                result = await session.run(query, from_id=str(from_id), to_id=str(to_id))
                record = await result.single()
                if record:
                    return record["path_nodes"]
        except Exception as exc:
            logger.error("Neo4j get_shortest_path failed: %s", exc)
        return None

    async def run_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute an arbitrary Cypher query and return all records as a list of
        plain dicts.  Useful for complex analytics queries.
        """
        if self._driver is None:
            return []
        try:
            async with self._driver.session() as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records
        except Exception as exc:
            logger.error("Neo4j run_query failed: %s", exc)
            return []

    async def delete_node(self, node_id: str) -> bool:
        """Detach-delete a node by its id property."""
        if self._driver is None:
            return False
        query = "MATCH (n {id: $id}) DETACH DELETE n"
        try:
            async with self._driver.session() as session:
                await session.run(query, id=str(node_id))
                return True
        except Exception as exc:
            logger.error("Neo4j delete_node failed: %s", exc)
            return False


# ── Module-level singleton helper ─────────────────────────────────────────────

_neo4j_instance: Optional[Neo4jAdapter] = None


def get_neo4j() -> Optional[Neo4jAdapter]:
    """
    Return a shared Neo4jAdapter instance, or None when Neo4j is not configured.

    Call this function rather than constructing Neo4jAdapter directly to
    benefit from the module-level connection pool reuse.
    """
    from config import settings

    if not settings.NEO4J_URL:
        return None

    global _neo4j_instance
    if _neo4j_instance is None:
        _neo4j_instance = Neo4jAdapter(
            url=settings.NEO4J_URL,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
    return _neo4j_instance
