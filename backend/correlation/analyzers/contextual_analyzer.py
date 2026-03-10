"""Contextual/semantic correlation analyzer."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from correlation.models.correlation import AnalysisResult

logger = logging.getLogger(__name__)

# Affinity matrix: how likely two entity types correlate
_TYPE_AFFINITY: Dict[str, Dict[str, float]] = {
    "person": {
        "person": 0.7,
        "organization": 0.6,
        "email": 0.8,
        "phone": 0.8,
        "location": 0.5,
        "cryptocurrency": 0.4,
        "vehicle": 0.4,
        "document": 0.5,
    },
    "organization": {
        "organization": 0.7,
        "person": 0.6,
        "domain": 0.7,
        "ip": 0.6,
        "location": 0.5,
        "email": 0.6,
    },
    "ip": {
        "ip": 0.8,
        "domain": 0.8,
        "organization": 0.5,
        "url": 0.7,
    },
    "domain": {
        "domain": 0.8,
        "ip": 0.8,
        "email": 0.7,
        "url": 0.9,
        "organization": 0.5,
    },
    "email": {
        "email": 0.9,
        "person": 0.7,
        "domain": 0.7,
    },
    "phone": {
        "phone": 0.8,
        "person": 0.7,
    },
    "url": {
        "url": 0.8,
        "domain": 0.9,
        "ip": 0.6,
    },
    "hash": {
        "hash": 0.9,
        "document": 0.6,
    },
    "cryptocurrency": {
        "cryptocurrency": 0.9,
        "person": 0.4,
        "organization": 0.4,
    },
    "location": {
        "location": 0.7,
        "person": 0.5,
        "organization": 0.5,
    },
    "vehicle": {
        "vehicle": 0.8,
        "person": 0.4,
    },
    "document": {
        "document": 0.8,
        "hash": 0.6,
        "person": 0.4,
    },
}

# Alias indicator attribute keys to compare
_ALIAS_ATTRS = ["name", "email", "phone", "ip", "username", "identifier"]


class ContextualAnalyzer:
    """Analyzes contextual and semantic correlations between entities."""

    ANALYZER_NAME = "contextual"

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    async def analyze(
        self,
        entity1: Any,
        entity2: Any,
        session: AsyncSession,
    ) -> AnalysisResult:
        """Analyze contextual correlation between two entities."""
        evidence: List[str] = []
        details: Dict[str, Any] = {}
        scores: List[float] = []

        try:
            # Type affinity
            affinity = self.compute_type_affinity(entity1.entity_type, entity2.entity_type)
            scores.append(affinity * 0.3)
            details["type_affinity"] = affinity

            # Attribute overlap
            attrs1 = entity1.attributes or {}
            attrs2 = entity2.attributes or {}
            attr_overlap = self.compute_attribute_overlap(attrs1, attrs2)
            scores.append(attr_overlap)
            details["attribute_overlap"] = attr_overlap
            if attr_overlap > 0.4:
                evidence.append(f"Significant attribute overlap (score={attr_overlap:.2f})")

            # Shared sources
            shared_sources = await self.find_shared_sources(entity1.id, entity2.id, session)
            if shared_sources:
                source_score = min(1.0, len(shared_sources) * 0.3)
                scores.append(source_score)
                details["shared_sources"] = [str(s) for s in shared_sources]
                evidence.append(f"Entities share {len(shared_sources)} common source(s)")

            # Common relationships (shared neighbors)
            common_rels = await self.find_common_relationships(entity1.id, entity2.id, session)
            if common_rels:
                neighbor_score = min(1.0, len(common_rels) * 0.2)
                scores.append(neighbor_score)
                details["common_neighbors"] = len(common_rels)
                evidence.append(f"Entities share {len(common_rels)} common neighbor(s)")

            # Alias detection
            alias_score = self.detect_alias_indicators(entity1, entity2)
            scores.append(alias_score)
            details["alias_score"] = alias_score
            if alias_score > 0.7:
                evidence.append(f"Strong alias indicators detected (score={alias_score:.2f})")

            # Geographic proximity (if applicable)
            geo_score = self.compute_geographic_proximity(entity1, entity2)
            if geo_score > 0.0:
                scores.append(geo_score)
                details["geographic_proximity"] = geo_score
                if geo_score > 0.6:
                    evidence.append(f"Geographic proximity detected (score={geo_score:.2f})")

            final_score = sum(scores) / len(scores) if scores else 0.0
            final_score = min(1.0, final_score)

        except Exception as exc:
            self.logger.warning("Contextual analysis failed: %s", exc)
            return AnalysisResult(
                score=0.0,
                evidence=[],
                details={"error": str(exc)},
                analyzer_name=self.ANALYZER_NAME,
            )

        return AnalysisResult(
            score=final_score,
            evidence=evidence,
            details=details,
            analyzer_name=self.ANALYZER_NAME,
        )

    def compute_attribute_overlap(
        self,
        e1_attrs: Dict[str, Any],
        e2_attrs: Dict[str, Any],
    ) -> float:
        """Compute attribute overlap between two attribute dicts using Jaccard similarity."""
        if not e1_attrs or not e2_attrs:
            return 0.0

        keys1 = set(e1_attrs.keys())
        keys2 = set(e2_attrs.keys())
        common_keys = keys1 & keys2
        all_keys = keys1 | keys2

        if not all_keys:
            return 0.0

        jaccard_keys = len(common_keys) / len(all_keys)

        if not common_keys:
            return jaccard_keys * 0.5

        matching_values = sum(
            1 for k in common_keys if str(e1_attrs.get(k)) == str(e2_attrs.get(k))
        )
        value_match = matching_values / len(common_keys)

        return (jaccard_keys + value_match) / 2.0

    async def find_shared_sources(
        self,
        entity1_id: UUID,
        entity2_id: UUID,
        session: AsyncSession,
    ) -> List[UUID]:
        """Find source IDs shared between two entities."""
        try:
            from storage.database.postgres.models import EntitySource

            stmt1 = select(EntitySource.source_id).where(
                EntitySource.entity_id == entity1_id
            )
            stmt2 = select(EntitySource.source_id).where(
                EntitySource.entity_id == entity2_id
            )

            res1 = await session.execute(stmt1)
            res2 = await session.execute(stmt2)

            sources1 = {r[0] for r in res1.all() if r[0]}
            sources2 = {r[0] for r in res2.all() if r[0]}

            return list(sources1 & sources2)
        except Exception as exc:
            self.logger.debug("Shared sources query failed: %s", exc)
            return []

    def compute_geographic_proximity(self, e1: Any, e2: Any) -> float:
        """Compute geographic proximity if both entities have lat/lon attributes.

        Returns 0.0 if location data unavailable, otherwise [0, 1].
        """
        attrs1 = e1.attributes or {}
        attrs2 = e2.attributes or {}

        lat1 = attrs1.get("latitude") or attrs1.get("lat")
        lon1 = attrs1.get("longitude") or attrs1.get("lon")
        lat2 = attrs2.get("latitude") or attrs2.get("lat")
        lon2 = attrs2.get("longitude") or attrs2.get("lon")

        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 0.0

        try:
            import math

            lat1, lon1, lat2, lon2 = (
                float(lat1),
                float(lon1),
                float(lat2),
                float(lon2),
            )
            # Haversine distance in km
            R = 6371.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1))
                * math.cos(math.radians(lat2))
                * math.sin(dlon / 2) ** 2
            )
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance_km = R * c

            # Score: 1.0 within 10km, decaying to 0 at 5000km
            return max(0.0, 1.0 - distance_km / 5000.0)
        except (ValueError, TypeError):
            return 0.0

    async def find_common_relationships(
        self,
        entity1_id: UUID,
        entity2_id: UUID,
        session: AsyncSession,
    ) -> List[UUID]:
        """Find entity IDs that are neighbors of both entity1 and entity2."""
        try:
            from storage.database.postgres.models import Relationship

            def neighbor_ids_query(eid: UUID):
                return select(Relationship.target_entity_id).where(
                    Relationship.source_entity_id == eid
                ).union(
                    select(Relationship.source_entity_id).where(
                        Relationship.target_entity_id == eid
                    )
                )

            res1 = await session.execute(neighbor_ids_query(entity1_id))
            res2 = await session.execute(neighbor_ids_query(entity2_id))

            neighbors1 = {r[0] for r in res1.all() if r[0]}
            neighbors2 = {r[0] for r in res2.all() if r[0]}

            # Exclude the entities themselves
            common = (neighbors1 & neighbors2) - {entity1_id, entity2_id}
            return list(common)
        except Exception as exc:
            self.logger.debug("Common relationships query failed: %s", exc)
            return []

    def compute_type_affinity(self, type1: str, type2: str) -> float:
        """Return type affinity score between two entity types."""
        row = _TYPE_AFFINITY.get(type1, {})
        return row.get(type2, 0.1)

    def detect_alias_indicators(self, e1: Any, e2: Any) -> float:
        """Detect alias likelihood based on matching names/identifiers.

        Returns a score in [0, 1].
        """
        scores: List[float] = []

        # Exact name match
        if e1.name and e2.name:
            if e1.name.lower().strip() == e2.name.lower().strip():
                return 1.0
            # Partial name overlap
            words1 = set(e1.name.lower().split())
            words2 = set(e2.name.lower().split())
            if words1 and words2:
                overlap = len(words1 & words2) / len(words1 | words2)
                scores.append(overlap)

        # Aliases list
        aliases1 = set(a.lower() for a in (e1.aliases or []))
        aliases2 = set(a.lower() for a in (e2.aliases or []))

        if e2.name and e2.name.lower() in aliases1:
            scores.append(0.9)
        if e1.name and e1.name.lower() in aliases2:
            scores.append(0.9)

        if aliases1 and aliases2:
            alias_overlap = len(aliases1 & aliases2) / len(aliases1 | aliases2)
            if alias_overlap > 0:
                scores.append(alias_overlap)

        # Attribute identifiers
        attrs1 = e1.attributes or {}
        attrs2 = e2.attributes or {}
        for key in _ALIAS_ATTRS:
            v1 = attrs1.get(key)
            v2 = attrs2.get(key)
            if v1 and v2 and str(v1).lower() == str(v2).lower():
                scores.append(0.8)

        if not scores:
            return 0.0
        return min(1.0, sum(scores) / len(scores))
