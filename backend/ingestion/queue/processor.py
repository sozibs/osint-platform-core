"""Ingestion record processor: normalizes raw records and stores entities."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database.postgres.models import Entity, EntitySource, Relationship, Source

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {
    "person", "organization", "location", "ip", "domain",
    "email", "phone", "url", "hash", "cryptocurrency",
    "vehicle", "document",
}


@dataclass
class NormalizedRecord:
    """A normalized data record ready for entity extraction."""

    entity_type: str
    name: str
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_url: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ProcessingResult:
    """Aggregated result of a batch processing operation."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    entities_created: int = 0
    relationships_created: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "entities_created": self.entities_created,
            "relationships_created": self.relationships_created,
            "errors": self.errors[:50],  # cap error list
            "duration_ms": round(self.duration_ms, 2),
        }


class IngestionProcessor:
    """Processes raw ingestion records: normalize → extract → store."""

    # ── Main entry point ──────────────────────────────────────────────────────

    async def process_records(
        self,
        records: List[Dict[str, Any]],
        source: Optional[Source],
        user_id: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Process a batch of raw records end-to-end.

        Returns a dict representation of ProcessingResult.
        """
        start = time.monotonic()
        result = ProcessingResult(total=len(records))

        for raw in records:
            try:
                normalized = await self.normalize_record(
                    raw, source.source_type if source else "unknown"
                )
                entities = await self.extract_entities(normalized)
                if not entities:
                    result.failed += 1
                    continue

                entity_ids = await self.store_entities(entities, source, session, user_id)
                result.entities_created += len(entity_ids)

                relationships = await self.extract_relationships(entities, raw)
                rel_ids = await self.store_relationships(relationships, session)
                result.relationships_created += len(rel_ids)

                result.successful += 1

            except Exception as exc:
                logger.warning("Error processing record: %s", exc)
                result.failed += 1
                result.errors.append(str(exc))

        try:
            await session.commit()
        except Exception as exc:
            logger.error("Failed to commit processing batch: %s", exc)
            await session.rollback()
            result.errors.append(f"Commit failed: {exc}")

        result.duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Processed %d records: %d ok, %d failed, %d entities, %d relationships.",
            result.total,
            result.successful,
            result.failed,
            result.entities_created,
            result.relationships_created,
        )
        return result.to_dict()

    # ── Normalization ─────────────────────────────────────────────────────────

    async def normalize_record(
        self, record: Dict[str, Any], source_type: str
    ) -> NormalizedRecord:
        """Map a raw record dict to a NormalizedRecord using heuristics."""
        from normalization.mappers.type_mapper import EntityTypeMapper
        from normalization.cleaners.data_cleaner import clean_entity_data

        mapper = EntityTypeMapper()
        entity_type = mapper.classify_entity(record)

        # Determine canonical name for this entity type
        name = self._extract_name(record, entity_type)
        if not name:
            raise ValueError(f"Cannot determine name for record: {list(record.keys())}")

        aliases: List[str] = []
        raw_aliases = record.get("aliases") or record.get("also_known_as") or []
        if isinstance(raw_aliases, list):
            aliases = [str(a) for a in raw_aliases if a]
        elif isinstance(raw_aliases, str) and raw_aliases:
            aliases = [raw_aliases]

        # Clean entity-specific attributes
        cleaned = clean_entity_data(entity_type, record)

        return NormalizedRecord(
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            attributes=cleaned,
            source_url=record.get("source_url") or record.get("url"),
            confidence=float(record.get("confidence", 1.0)),
        )

    def _extract_name(self, record: Dict[str, Any], entity_type: str) -> str:
        """Extract the primary name for an entity type from a raw record."""
        type_name_fields: Dict[str, List[str]] = {
            "person": ["name", "full_name", "person_name", "username"],
            "organization": ["name", "org_name", "company", "organization"],
            "location": ["name", "location", "address", "place"],
            "ip": ["ip", "ip_address", "address", "value"],
            "domain": ["domain", "hostname", "fqdn", "value"],
            "email": ["email", "email_address", "value"],
            "phone": ["phone", "phone_number", "telephone", "value"],
            "url": ["url", "link", "href", "value"],
            "hash": ["hash", "hash_value", "md5", "sha1", "sha256", "value"],
            "cryptocurrency": ["address", "wallet", "value"],
            "vehicle": ["name", "plate", "license_plate", "vin", "value"],
            "document": ["title", "name", "filename", "value"],
        }

        for field_name in type_name_fields.get(entity_type, ["name", "value", "title"]):
            val = record.get(field_name)
            if val and isinstance(val, str) and val.strip():
                return val.strip()

        # Fallback: first non-empty string value
        for val in record.values():
            if isinstance(val, str) and val.strip():
                return val.strip()

        return ""

    # ── Entity extraction ─────────────────────────────────────────────────────

    async def extract_entities(
        self, normalized: NormalizedRecord
    ) -> List[NormalizedRecord]:
        """For a normalized record, return one or more entity candidates.

        Currently returns the single entity represented by the record.
        Can be extended for compound records (e.g. person + organization).
        """
        if not normalized.name or normalized.entity_type not in VALID_ENTITY_TYPES:
            return []
        return [normalized]

    # ── Relationship extraction ───────────────────────────────────────────────

    async def extract_relationships(
        self, entities: List[NormalizedRecord], raw: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Derive relationships from entity attributes and raw record fields.

        Returns a list of relationship dicts ready for storage.
        """
        relationships: List[Dict[str, Any]] = []

        if len(entities) < 2:
            return relationships

        # For compound records, create a generic "associated_with" link
        for i in range(len(entities) - 1):
            relationships.append({
                "source_entity_name": entities[i].name,
                "source_entity_type": entities[i].entity_type,
                "target_entity_name": entities[i + 1].name,
                "target_entity_type": entities[i + 1].entity_type,
                "relationship_type": "associated_with",
                "attributes": {},
                "confidence_score": min(entities[i].confidence, entities[i + 1].confidence),
            })

        return relationships

    # ── Storage ───────────────────────────────────────────────────────────────

    async def store_entities(
        self,
        entities: List[NormalizedRecord],
        source: Optional[Source],
        session: AsyncSession,
        user_id: str,
    ) -> List[UUID]:
        """Persist entities to the database, updating existing ones if found.

        Returns a list of entity UUIDs that were created or updated.
        """
        entity_ids: List[UUID] = []
        user_uuid: Optional[uuid.UUID] = None
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            pass

        for norm in entities:
            try:
                # Check for existing canonical entity by type + name
                stmt = select(Entity).where(
                    Entity.entity_type == norm.entity_type,
                    Entity.name == norm.name,
                    Entity.is_canonical.is_(True),
                )
                existing_result = await session.execute(stmt)
                existing: Optional[Entity] = existing_result.scalar_one_or_none()

                if existing:
                    # Merge aliases
                    existing_aliases: List[str] = list(existing.aliases or [])
                    for alias in norm.aliases:
                        if alias not in existing_aliases:
                            existing_aliases.append(alias)
                    existing.aliases = existing_aliases

                    # Merge attributes (non-destructive)
                    existing_attrs: Dict[str, Any] = dict(existing.attributes or {})
                    for k, v in norm.attributes.items():
                        if k not in existing_attrs or not existing_attrs[k]:
                            existing_attrs[k] = v
                    existing.attributes = existing_attrs

                    # Update confidence if higher
                    if norm.confidence > (existing.confidence_score or 0.0):
                        existing.confidence_score = norm.confidence

                    entity = existing
                else:
                    entity = Entity(
                        entity_type=norm.entity_type,
                        name=norm.name,
                        aliases=norm.aliases,
                        attributes=norm.attributes,
                        confidence_score=norm.confidence,
                        is_canonical=True,
                        created_by=user_uuid,
                    )
                    session.add(entity)
                    await session.flush()  # get the generated ID

                entity_ids.append(entity.id)

                # Link entity to source
                if source:
                    link_stmt = select(EntitySource).where(
                        EntitySource.entity_id == entity.id,
                        EntitySource.source_id == source.id,
                    )
                    link_result = await session.execute(link_stmt)
                    if not link_result.scalar_one_or_none():
                        es = EntitySource(
                            entity_id=entity.id,
                            source_id=source.id,
                            raw_data=norm.attributes,
                            confidence_score=norm.confidence,
                        )
                        session.add(es)

            except Exception as exc:
                logger.error("Failed to store entity %s (%s): %s", norm.name, norm.entity_type, exc)
                raise

        return entity_ids

    async def store_relationships(
        self,
        relationships: List[Dict[str, Any]],
        session: AsyncSession,
    ) -> List[UUID]:
        """Persist relationships between entities.

        Looks up entity IDs by name+type, skips if either entity is not found.
        """
        rel_ids: List[UUID] = []

        for rel in relationships:
            try:
                src_stmt = select(Entity).where(
                    Entity.name == rel["source_entity_name"],
                    Entity.entity_type == rel["source_entity_type"],
                    Entity.is_canonical.is_(True),
                )
                src_result = await session.execute(src_stmt)
                src_entity = src_result.scalar_one_or_none()

                tgt_stmt = select(Entity).where(
                    Entity.name == rel["target_entity_name"],
                    Entity.entity_type == rel["target_entity_type"],
                    Entity.is_canonical.is_(True),
                )
                tgt_result = await session.execute(tgt_stmt)
                tgt_entity = tgt_result.scalar_one_or_none()

                if not src_entity or not tgt_entity:
                    continue

                # Avoid duplicate relationships
                dup_stmt = select(Relationship).where(
                    Relationship.source_entity_id == src_entity.id,
                    Relationship.target_entity_id == tgt_entity.id,
                    Relationship.relationship_type == rel["relationship_type"],
                )
                dup_result = await session.execute(dup_stmt)
                if dup_result.scalar_one_or_none():
                    continue

                db_rel = Relationship(
                    source_entity_id=src_entity.id,
                    target_entity_id=tgt_entity.id,
                    relationship_type=rel["relationship_type"],
                    attributes=rel.get("attributes", {}),
                    confidence_score=rel.get("confidence_score", 1.0),
                )
                session.add(db_rel)
                await session.flush()
                rel_ids.append(db_rel.id)

            except Exception as exc:
                logger.error("Failed to store relationship %s: %s", rel, exc)

        return rel_ids
