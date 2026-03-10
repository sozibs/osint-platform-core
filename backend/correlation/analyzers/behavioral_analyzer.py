"""Behavioral pattern analyzer."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from correlation.models.correlation import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class SharedInfra:
    """Shared infrastructure between entities."""

    entities: List[UUID]
    infrastructure_type: str
    evidence: List[str]


@dataclass
class CommunicationPattern:
    """Communication pattern between entities."""

    entities: List[UUID]
    pattern_type: str
    frequency: float
    confidence: float


class BehavioralAnalyzer:
    """Analyzes behavioral correlations between entities."""

    ANALYZER_NAME = "behavioral"

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    async def analyze(
        self,
        entity1: Any,
        entity2: Any,
        session: AsyncSession,
    ) -> AnalysisResult:
        """Analyze behavioral correlation between two entities."""
        evidence: List[str] = []
        details: Dict[str, Any] = {}
        scores: List[float] = []

        try:
            # Behavioral similarity from attributes
            sim = self.compute_behavioral_similarity(entity1, entity2)
            scores.append(sim)
            details["attribute_similarity"] = sim
            if sim > 0.5:
                evidence.append(f"High attribute similarity detected (score={sim:.2f})")

            # Shared infrastructure
            shared = await self.detect_shared_infrastructure([entity1, entity2])
            if shared:
                infra_score = min(1.0, len(shared) * 0.3)
                scores.append(infra_score)
                details["shared_infrastructure"] = [
                    {"type": s.infrastructure_type, "evidence": s.evidence} for s in shared
                ]
                evidence.extend(
                    [f"Shared infrastructure: {s.infrastructure_type}" for s in shared]
                )

            # Communication patterns
            comm_patterns = await self.find_communication_patterns(
                [entity1.id, entity2.id], session
            )
            if comm_patterns:
                comm_score = min(1.0, sum(p.confidence for p in comm_patterns) / len(comm_patterns))
                scores.append(comm_score)
                details["communication_patterns"] = len(comm_patterns)
                evidence.append(f"Found {len(comm_patterns)} communication pattern(s)")

            final_score = sum(scores) / len(scores) if scores else 0.0
            final_score = min(1.0, final_score)

        except Exception as exc:
            self.logger.warning("Behavioral analysis failed: %s", exc)
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

    def compare_activity_patterns(
        self,
        e1_logs: List[Dict[str, Any]],
        e2_logs: List[Dict[str, Any]],
    ) -> float:
        """Compare activity log patterns between two entities.

        Returns a similarity score in [0, 1].
        """
        if not e1_logs or not e2_logs:
            return 0.0

        e1_types = {log.get("action") or log.get("type") for log in e1_logs if log}
        e2_types = {log.get("action") or log.get("type") for log in e2_logs if log}
        e1_types.discard(None)
        e2_types.discard(None)

        if not e1_types or not e2_types:
            return 0.0

        intersection = e1_types & e2_types
        union = e1_types | e2_types
        jaccard = len(intersection) / len(union) if union else 0.0
        return jaccard

    async def detect_shared_infrastructure(
        self,
        entities: List[Any],
    ) -> List[SharedInfra]:
        """Detect shared infrastructure (IP, hosting, etc.) between entities."""
        shared: List[SharedInfra] = []

        if len(entities) < 2:
            return shared

        # Group by ip attribute
        ip_map: Dict[str, List[UUID]] = {}
        asn_map: Dict[str, List[UUID]] = {}
        hosting_map: Dict[str, List[UUID]] = {}

        for entity in entities:
            attrs = entity.attributes or {}
            ip = attrs.get("ip") or attrs.get("ip_address")
            asn = attrs.get("asn") or attrs.get("autonomous_system")
            hosting = attrs.get("hosting_provider") or attrs.get("registrar")

            if ip:
                ip_map.setdefault(ip, []).append(entity.id)
            if asn:
                asn_map.setdefault(str(asn), []).append(entity.id)
            if hosting:
                hosting_map.setdefault(hosting, []).append(entity.id)

        for ip, eids in ip_map.items():
            if len(eids) > 1:
                shared.append(
                    SharedInfra(
                        entities=eids,
                        infrastructure_type="shared_ip",
                        evidence=[f"Shared IP address: {ip}"],
                    )
                )

        for asn, eids in asn_map.items():
            if len(eids) > 1:
                shared.append(
                    SharedInfra(
                        entities=eids,
                        infrastructure_type="shared_asn",
                        evidence=[f"Shared ASN: {asn}"],
                    )
                )

        for provider, eids in hosting_map.items():
            if len(eids) > 1:
                shared.append(
                    SharedInfra(
                        entities=eids,
                        infrastructure_type="shared_hosting",
                        evidence=[f"Shared hosting provider: {provider}"],
                    )
                )

        return shared

    async def find_communication_patterns(
        self,
        entity_ids: List[UUID],
        session: AsyncSession,
    ) -> List[CommunicationPattern]:
        """Find communication patterns between entities."""
        if len(entity_ids) < 2:
            return []

        try:
            from storage.database.postgres.models import Relationship

            stmt = select(Relationship).where(
                Relationship.source_entity_id.in_(entity_ids),
                Relationship.target_entity_id.in_(entity_ids),
                Relationship.relationship_type == "communicates_with",
            )
            result = await session.execute(stmt)
            rels = result.scalars().all()
        except Exception as exc:
            self.logger.debug("Communication pattern query failed: %s", exc)
            return []

        patterns: List[CommunicationPattern] = []
        if rels:
            patterns.append(
                CommunicationPattern(
                    entities=entity_ids,
                    pattern_type="direct_communication",
                    frequency=float(len(rels)),
                    confidence=min(1.0, len(rels) * 0.25),
                )
            )

        return patterns

    def compute_behavioral_similarity(self, e1: Any, e2: Any) -> float:
        """Compute behavioral similarity based on entity attributes."""
        attrs1: Dict[str, Any] = e1.attributes or {}
        attrs2: Dict[str, Any] = e2.attributes or {}

        if not attrs1 or not attrs2:
            return 0.0

        keys1 = set(attrs1.keys())
        keys2 = set(attrs2.keys())
        common_keys = keys1 & keys2

        if not common_keys:
            return 0.0

        matching_values = sum(
            1 for k in common_keys if str(attrs1.get(k)) == str(attrs2.get(k))
        )

        jaccard_keys = len(common_keys) / len(keys1 | keys2)
        value_match = matching_values / len(common_keys) if common_keys else 0.0

        return (jaccard_keys + value_match) / 2.0

    async def detect_coordinated_activity(
        self,
        entity_ids: List[UUID],
        time_window: float,
        session: AsyncSession,
    ) -> float:
        """Detect coordinated (synchronized) activity among entities.

        Returns coordination score in [0, 1].
        """
        if len(entity_ids) < 2:
            return 0.0

        try:
            from storage.database.postgres.models import Relationship

            stmt = (
                select(Relationship.source_entity_id, Relationship.created_at)
                .where(Relationship.source_entity_id.in_(entity_ids))
                .order_by(Relationship.created_at)
            )
            result = await session.execute(stmt)
            rows = result.all()
        except Exception as exc:
            self.logger.debug("Coordinated activity query failed: %s", exc)
            return 0.0

        if len(rows) < 2:
            return 0.0

        # Count pairs that acted within time_window of each other
        coordinated_pairs = 0
        total_pairs = 0

        for i, (eid1, ts1) in enumerate(rows):
            for eid2, ts2 in rows[i + 1 :]:
                if eid1 == eid2:
                    continue
                total_pairs += 1
                diff = abs((ts1 - ts2).total_seconds())
                if diff <= time_window:
                    coordinated_pairs += 1

        if total_pairs == 0:
            return 0.0

        return coordinated_pairs / total_pairs
