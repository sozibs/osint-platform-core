"""Correlation Engine - finds relationships between entities."""
from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
from ..analyzers.temporal_analyzer import TemporalAnalyzer
from ..analyzers.behavioral_analyzer import BehavioralAnalyzer
from ..analyzers.contextual_analyzer import ContextualAnalyzer
from ..scoring.relationship_scorer import RelationshipScorer
from ..models.correlation import Correlation

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Orchestrates entity correlation across multiple analysis dimensions."""

    def __init__(self) -> None:
        self.temporal = TemporalAnalyzer()
        self.behavioral = BehavioralAnalyzer()
        self.contextual = ContextualAnalyzer()
        self.scorer = RelationshipScorer()

    async def correlate(
        self, entity_a: dict[str, Any], entity_b: dict[str, Any]
    ) -> Correlation:
        """Compute full correlation between two entities."""
        temporal_score = await self.temporal.analyze(entity_a, entity_b)
        behavioral_score = await self.behavioral.analyze(entity_a, entity_b)
        contextual_score = await self.contextual.analyze(entity_a, entity_b)
        overall = self.scorer.score(temporal_score, behavioral_score, contextual_score)
        return Correlation(
            entity_a_id=entity_a.get("entity_id"),
            entity_b_id=entity_b.get("entity_id"),
            temporal_score=temporal_score,
            behavioral_score=behavioral_score,
            contextual_score=contextual_score,
            overall_score=overall,
        )

    async def bulk_correlate(
        self, entities: list[dict[str, Any]]
    ) -> list[Correlation]:
        """Correlate all pairs of entities."""
        results: list[Correlation] = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                try:
                    c = await self.correlate(entities[i], entities[j])
                    if c.overall_score > 0.1:
                        results.append(c)
                except Exception as exc:
                    logger.warning("Correlation failed for pair %d-%d: %s", i, j, exc)
        return results
