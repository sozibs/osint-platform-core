"""Investigation plugin implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from plugins.interfaces.plugin_interface import PluginInterface

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class InvestigationPlugin(PluginInterface):
    @property
    def name(self) -> str:
        return "investigation"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Comprehensive person and organization investigation workflows."

    def initialize(self) -> None:
        logger.info("Investigation module initialized")

    def register_routes(self, app: "FastAPI") -> None:
        from .api.routes import router

        app.include_router(
            router,
            prefix="/api/v1/modules/investigation",
            tags=["investigation"],
        )

    def register_entity_types(self) -> List[str]:
        return ["person_profile", "org_profile", "public_record", "media_mention"]

    def register_relationship_types(self) -> List[str]:
        return ["employment", "affiliation", "association", "family"]

    def get_capabilities(self) -> List[str]:
        return ["data-ingestion", "entity-creation", "relationship-discovery", "case-management"]

    def get_permissions_required(self) -> List[str]:
        return ["read_entities", "write_entities", "manage_cases"]
