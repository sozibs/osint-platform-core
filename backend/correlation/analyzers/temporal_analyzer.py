"""Temporal correlation analyzer."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from correlation.models.correlation import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class TemporalCluster:
    """A cluster of temporally co-occurring entities."""

    entity_ids: List[UUID]
    start_time: datetime
    end_time: datetime
    activity_count: int


@dataclass
class Period:
    """A detected periodic activity pattern."""

    entity_id: UUID
    interval_seconds: float
    confidence: float
    sample_count: int


class TemporalAnalyzer:
    """Analyzes temporal correlations between entities."""

    ANALYZER_NAME = "temporal"
    MAX_TIME_WINDOW_SECONDS = 3600  # 1 hour default window

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    async def analyze(
        self,
        entity1: Any,
        entity2: Any,
        session: AsyncSession,
    ) -> AnalysisResult:
        """Analyze temporal correlation between two entities."""
        evidence: List[str] = []
        details: Dict[str, Any] = {}
        scores: List[float] = []

        try:
            # Co-occurrence in a 1-hour window
            co_score = await self.detect_co_occurrence(
                entity1.id, entity2.id, self.MAX_TIME_WINDOW_SECONDS, session
            )
            scores.append(co_score)
            details["co_occurrence_score"] = co_score
            if co_score > 0.5:
                evidence.append(
                    f"Entities co-occurred within {self.MAX_TIME_WINDOW_SECONDS}s window "
                    f"(score={co_score:.2f})"
                )

            # Creation-time proximity
            if entity1.created_at and entity2.created_at:
                dist = self.compute_temporal_distance(entity1.created_at, entity2.created_at)
                proximity = max(0.0, 1.0 - dist)
                scores.append(proximity * 0.5)
                details["creation_time_proximity"] = proximity
                if proximity > 0.7:
                    evidence.append(
                        f"Entities created within close temporal proximity (score={proximity:.2f})"
                    )

            # Update-time proximity
            if entity1.updated_at and entity2.updated_at:
                dist = self.compute_temporal_distance(entity1.updated_at, entity2.updated_at)
                proximity = max(0.0, 1.0 - dist)
                scores.append(proximity * 0.3)
                details["update_time_proximity"] = proximity

            final_score = sum(scores) / len(scores) if scores else 0.0
            final_score = min(1.0, final_score)

        except Exception as exc:
            self.logger.warning("Temporal analysis failed: %s", exc)
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

    def find_temporal_overlap(
        self,
        e1_events: List[datetime],
        e2_events: List[datetime],
        window_seconds: float = 3600.0,
    ) -> float:
        """Compute overlap score between two lists of event timestamps.

        Returns a value in [0, 1] representing how much the event streams
        overlap within the given time window.
        """
        if not e1_events or not e2_events:
            return 0.0

        overlapping = 0
        total = len(e1_events)

        for ts1 in e1_events:
            for ts2 in e2_events:
                delta = abs((ts1 - ts2).total_seconds())
                if delta <= window_seconds:
                    overlapping += 1
                    break

        return overlapping / total

    async def detect_co_occurrence(
        self,
        entity1_id: UUID,
        entity2_id: UUID,
        window_seconds: float,
        session: AsyncSession,
    ) -> float:
        """Detect how often the two entities appear together within a time window.

        Uses relationship creation timestamps as proxy for co-occurrence events.
        Returns a score in [0, 1].
        """
        try:
            from storage.database.postgres.models import Relationship

            stmt1 = select(Relationship.created_at).where(
                (Relationship.source_entity_id == entity1_id)
                | (Relationship.target_entity_id == entity1_id)
            )
            stmt2 = select(Relationship.created_at).where(
                (Relationship.source_entity_id == entity2_id)
                | (Relationship.target_entity_id == entity2_id)
            )

            result1 = await session.execute(stmt1)
            result2 = await session.execute(stmt2)

            times1: List[datetime] = [r[0] for r in result1.all() if r[0]]
            times2: List[datetime] = [r[0] for r in result2.all() if r[0]]

            return self.find_temporal_overlap(times1, times2, window_seconds)
        except Exception as exc:
            self.logger.debug("co_occurrence query failed: %s", exc)
            return 0.0

    async def find_activity_clusters(
        self,
        entity_ids: List[UUID],
        session: AsyncSession,
        window_seconds: float = 3600.0,
    ) -> List[TemporalCluster]:
        """Group entities into temporal activity clusters."""
        if not entity_ids:
            return []

        try:
            from storage.database.postgres.models import Entity

            stmt = select(Entity.id, Entity.created_at, Entity.updated_at).where(
                Entity.id.in_(entity_ids)
            )
            result = await session.execute(stmt)
            rows = result.all()
        except Exception as exc:
            self.logger.warning("Activity cluster query failed: %s", exc)
            return []

        # Build (entity_id, timestamp) pairs
        events: List[tuple[UUID, datetime]] = []
        for row in rows:
            eid, created, updated = row
            if created:
                events.append((eid, created))
            if updated and updated != created:
                events.append((eid, updated))

        if not events:
            return []

        events.sort(key=lambda x: x[1])

        clusters: List[TemporalCluster] = []
        current_cluster_entities: List[UUID] = [events[0][0]]
        cluster_start = events[0][1]
        cluster_end = events[0][1]

        for eid, ts in events[1:]:
            if (ts - cluster_end).total_seconds() <= window_seconds:
                if eid not in current_cluster_entities:
                    current_cluster_entities.append(eid)
                cluster_end = max(cluster_end, ts)
            else:
                if len(current_cluster_entities) > 1:
                    clusters.append(
                        TemporalCluster(
                            entity_ids=list(current_cluster_entities),
                            start_time=cluster_start,
                            end_time=cluster_end,
                            activity_count=len(current_cluster_entities),
                        )
                    )
                current_cluster_entities = [eid]
                cluster_start = ts
                cluster_end = ts

        if len(current_cluster_entities) > 1:
            clusters.append(
                TemporalCluster(
                    entity_ids=list(current_cluster_entities),
                    start_time=cluster_start,
                    end_time=cluster_end,
                    activity_count=len(current_cluster_entities),
                )
            )

        return clusters

    def compute_temporal_distance(self, dt1: datetime, dt2: datetime) -> float:
        """Compute a normalized temporal distance between two datetimes.

        Returns 0.0 if identical, approaching 1.0 as distance grows (sigmoid-like).
        Uses a reference scale of 30 days.
        """
        diff_seconds = abs((dt1 - dt2).total_seconds())
        # Normalize: 0 => 0.0, 30 days => ~0.86
        reference_seconds = 30 * 24 * 3600
        return 1.0 - math.exp(-diff_seconds / reference_seconds)

    async def detect_periodic_activity(
        self,
        entity_id: UUID,
        session: AsyncSession,
    ) -> Optional[Period]:
        """Detect periodic activity pattern for an entity.

        Looks at relationship creation timestamps and computes inter-event
        intervals to find regularity.
        """
        try:
            from storage.database.postgres.models import Relationship

            stmt = (
                select(Relationship.created_at)
                .where(
                    (Relationship.source_entity_id == entity_id)
                    | (Relationship.target_entity_id == entity_id)
                )
                .order_by(Relationship.created_at)
            )
            result = await session.execute(stmt)
            timestamps = [r[0] for r in result.all() if r[0]]
        except Exception as exc:
            self.logger.debug("Periodic activity query failed: %s", exc)
            return None

        if len(timestamps) < 3:
            return None

        intervals = [
            (timestamps[i + 1] - timestamps[i]).total_seconds()
            for i in range(len(timestamps) - 1)
        ]

        mean_interval = sum(intervals) / len(intervals)
        if mean_interval <= 0:
            return None

        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_interval  # Coefficient of variation

        # Low CV = more periodic
        confidence = max(0.0, 1.0 - cv)

        if confidence < 0.3:
            return None

        return Period(
            entity_id=entity_id,
            interval_seconds=mean_interval,
            confidence=confidence,
            sample_count=len(intervals),
        )
