"""Digital Footprint plugin implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from plugins.interfaces.plugin_interface import PluginInterface

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class DigitalFootprintPlugin(PluginInterface):
    @property
    def name(self) -> str:
        return "digital-footprint"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Track and correlate digital identities across the internet."

    def initialize(self) -> None:
        logger.info("Digital Footprint module initialized")

    def register_routes(self, app: "FastAPI") -> None:
        from .api.routes import router

        app.include_router(
            router,
            prefix="/api/v1/modules/digital-footprint",
            tags=["digital-footprint"],
        )

    def register_entity_types(self) -> List[str]:
        return ["social_profile", "email_record", "phone_record", "username_record", "domain_record"]

    def register_relationship_types(self) -> List[str]:
        return ["identity_link", "platform_association"]

    def get_capabilities(self) -> List[str]:
        return ["data-ingestion", "entity-creation", "relationship-discovery"]

    def get_permissions_required(self) -> List[str]:
        return ["read_entities", "write_entities"]

    async def on_entity_created(self, entity: Dict[str, Any]) -> None:
        logger.debug("Digital Footprint: entity created: %s", entity.get("id"))

    async def on_entity_updated(self, entity: Dict[str, Any]) -> None:
        logger.debug("Digital Footprint: entity updated: %s", entity.get("id"))

    def cleanup(self) -> None:
        logger.info("Digital Footprint module cleaned up")
