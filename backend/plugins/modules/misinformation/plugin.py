"""Misinformation plugin implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from plugins.interfaces.plugin_interface import PluginInterface

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class MisinformationPlugin(PluginInterface):
    @property
    def name(self) -> str:
        return "misinformation"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Track, analyze, and combat misinformation and disinformation campaigns."

    def initialize(self) -> None:
        logger.info("Misinformation module initialized")

    def register_routes(self, app: "FastAPI") -> None:
        from .api.routes import router

        app.include_router(
            router,
            prefix="/api/v1/modules/misinformation",
            tags=["misinformation"],
        )

    def register_entity_types(self) -> List[str]:
        return ["claim", "narrative", "factcheck", "misinformation_campaign", "source_rating"]

    def register_relationship_types(self) -> List[str]:
        return ["claim_supports", "claim_contradicts", "narrative_contains", "source_rates"]

    def get_capabilities(self) -> List[str]:
        return ["data-ingestion", "entity-creation", "claim-detection", "fact-checking", "narrative-analysis"]

    def get_permissions_required(self) -> List[str]:
        return ["read_entities", "write_entities"]

    async def on_entity_created(self, entity: Dict[str, Any]) -> None:
        logger.debug("Misinformation: entity created: %s", entity.get("id"))

    async def on_entity_updated(self, entity: Dict[str, Any]) -> None:
        logger.debug("Misinformation: entity updated: %s", entity.get("id"))

    def cleanup(self) -> None:
        logger.info("Misinformation module cleaned up")
