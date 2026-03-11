"""Cyber OSINT plugin implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from plugins.interfaces.plugin_interface import PluginInterface

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class CyberOsintPlugin(PluginInterface):
    @property
    def name(self) -> str:
        return "cyber-osint"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Technical intelligence gathering on digital infrastructure and cybersecurity."

    def initialize(self) -> None:
        logger.info("Cyber OSINT module initialized")

    def register_routes(self, app: "FastAPI") -> None:
        from .api.routes import router

        app.include_router(
            router,
            prefix="/api/v1/modules/cyber-osint",
            tags=["cyber-osint"],
        )

    def register_entity_types(self) -> List[str]:
        return ["ip_record", "cyber_domain_record", "certificate", "threat_indicator"]

    def register_relationship_types(self) -> List[str]:
        return ["hosts", "resolves_to", "shares_infrastructure", "associated_threat"]

    def get_capabilities(self) -> List[str]:
        return ["data-ingestion", "entity-creation", "threat-intelligence", "infrastructure-mapping"]

    def get_permissions_required(self) -> List[str]:
        return ["read_entities", "write_entities"]

    async def on_entity_created(self, entity: Dict[str, Any]) -> None:
        logger.debug("Cyber OSINT: entity created: %s", entity.get("id"))

    async def on_entity_updated(self, entity: Dict[str, Any]) -> None:
        logger.debug("Cyber OSINT: entity updated: %s", entity.get("id"))

    def cleanup(self) -> None:
        logger.info("Cyber OSINT module cleaned up")
