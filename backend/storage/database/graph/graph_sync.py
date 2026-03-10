"""
Graph synchronisation service.

Keeps Neo4j in sync with the canonical entities and relationships stored in
PostgreSQL.  All operations degrade gracefully when Neo4j is not available.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from storage.database.graph.neo4j_adapter import Neo4jAdapter, get_neo4j

logger = logging.getLogger(__name__)


class GraphSyncService:
    """
    Synchronises PostgreSQL entity/relationship data into Neo4j.

    Each public method accepts ORM model instances (or raw dicts) so that the
    service can be called from Celery tasks, FastAPI endpoints, or migration
    scripts without coupling to a specific import path.
    """

    def __init__(self, adapter: Neo4jAdapter | None = None) -> None:
        self._adapter = adapter or get_neo4j()

    @property
    def _available(self) -> bool:
        return self._adapter is not None

    # ── Entity sync ───────────────────────────────────────────────────────────

    async def sync_entity(self, entity: object) -> bool:
        """
        Create or update a Neo4j node for the given Entity ORM instance.

        Returns True on success, False when Neo4j is unavailable or an error
        occurs (caller should handle gracefully – Neo4j is a secondary store).
        """
        if not self._available or self._adapter is None:
            return False

        try:
            entity_id = str(getattr(entity, "id", ""))
            entity_type = getattr(entity, "entity_type", "Unknown")
            name = getattr(entity, "name", "")
            confidence = getattr(entity, "confidence_score", 1.0)
            is_canonical = getattr(entity, "is_canonical", True)

            label = _sanitise_label(entity_type)

            properties = {
                "id": entity_id,
                "name": name,
                "entity_type": entity_type,
                "confidence_score": str(confidence),
                "is_canonical": str(is_canonical),
            }

            # Also tag with the generic Entity label for cross-type queries
            result = await self._adapter.run_query(
                f"MERGE (n:Entity:{label} {{id: $id}}) SET n += $props RETURN n",
                {"id": entity_id, "props": properties},
            )
            logger.debug("Synced entity %s (%s) to Neo4j", entity_id, entity_type)
            return bool(result is not None)
        except Exception as exc:
            logger.warning("graph sync_entity failed: %s", exc)
            return False

    # ── Relationship sync ─────────────────────────────────────────────────────

    async def sync_relationship(self, relationship: object) -> bool:
        """
        Create or update a Neo4j relationship for the given Relationship ORM instance.
        """
        if not self._available or self._adapter is None:
            return False

        try:
            from_id = str(getattr(relationship, "source_entity_id", ""))
            to_id = str(getattr(relationship, "target_entity_id", ""))
            rel_type = getattr(relationship, "relationship_type", "RELATED_TO")
            rel_id = str(getattr(relationship, "id", ""))
            confidence = getattr(relationship, "confidence_score", 1.0)
            is_directed = getattr(relationship, "is_directed", True)

            safe_rel_type = _sanitise_label(rel_type.upper())
            props = {
                "id": rel_id,
                "confidence_score": str(confidence),
                "is_directed": str(is_directed),
            }

            result = await self._adapter.create_relationship(
                from_id=from_id,
                to_id=to_id,
                rel_type=safe_rel_type,
                properties=props,
            )
            logger.debug(
                "Synced relationship %s (%s -> %s) to Neo4j", rel_id, from_id, to_id
            )
            return result is not None
        except Exception as exc:
            logger.warning("graph sync_relationship failed: %s", exc)
            return False

    # ── Deletion sync ─────────────────────────────────────────────────────────

    async def sync_entity_deletion(self, entity_id: UUID | str) -> bool:
        """Remove the node (and all its relationships) from Neo4j."""
        if not self._available or self._adapter is None:
            return False
        try:
            deleted = await self._adapter.delete_node(str(entity_id))
            logger.debug("Deleted entity %s from Neo4j", entity_id)
            return deleted
        except Exception as exc:
            logger.warning("graph sync_entity_deletion failed: %s", exc)
            return False

    # ── Full sync ─────────────────────────────────────────────────────────────

    async def full_sync(self, session: AsyncSession) -> dict:
        """
        Iterate over all entities and relationships in PostgreSQL and mirror
        them into Neo4j.  This is intended for initial population or recovery
        scenarios, not for routine operation.

        Returns a summary dict with counts of synced/failed records.
        """
        if not self._available:
            logger.info("Neo4j not available; skipping full_sync")
            return {"entities_synced": 0, "relationships_synced": 0, "errors": 0}

        from sqlalchemy import select
        from storage.database.postgres.models import Entity, Relationship

        entities_synced = 0
        relationships_synced = 0
        errors = 0

        # ── Entities ──────────────────────────────────────────────────────
        entity_result = await session.execute(select(Entity))
        entities = entity_result.scalars().all()
        for entity in entities:
            success = await self.sync_entity(entity)
            if success:
                entities_synced += 1
            else:
                errors += 1

        # ── Relationships ─────────────────────────────────────────────────
        rel_result = await session.execute(select(Relationship))
        relationships = rel_result.scalars().all()
        for rel in relationships:
            success = await self.sync_relationship(rel)
            if success:
                relationships_synced += 1
            else:
                errors += 1

        summary = {
            "entities_synced": entities_synced,
            "relationships_synced": relationships_synced,
            "errors": errors,
        }
        logger.info("full_sync complete: %s", summary)
        return summary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitise_label(label: str) -> str:
    """
    Convert an arbitrary string into a valid Neo4j label / relationship type.

    Replaces non-alphanumeric characters with underscores and ensures the
    label starts with a letter.
    """
    import re
    sanitised = re.sub(r"[^a-zA-Z0-9_]", "_", label)
    if sanitised and sanitised[0].isdigit():
        sanitised = "L_" + sanitised
    return sanitised or "Unknown"
