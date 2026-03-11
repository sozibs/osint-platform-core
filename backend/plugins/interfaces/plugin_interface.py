from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class PluginInterface(abc.ABC):
    """Abstract base class that all OSINT platform plugins must implement."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique plugin name."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Plugin version string."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable plugin description."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize module resources."""

    @abc.abstractmethod
    def register_routes(self, app: "FastAPI") -> None:
        """Register API routes with the FastAPI application."""

    @abc.abstractmethod
    def register_entity_types(self) -> List[str]:
        """Returns list of custom entity type names provided by this plugin."""

    @abc.abstractmethod
    def register_relationship_types(self) -> List[str]:
        """Returns list of custom relationship type names provided by this plugin."""

    async def on_entity_created(self, entity: Dict[str, Any]) -> None:
        """Hook called when an entity is created. Default is a no-op."""

    async def on_entity_updated(self, entity: Dict[str, Any]) -> None:
        """Hook called when an entity is updated. Default is a no-op."""

    def cleanup(self) -> None:
        """Release any resources held by the plugin. Default is a no-op."""

    def get_capabilities(self) -> List[str]:
        """Returns a list of capability identifiers this plugin provides."""
        return []

    def get_permissions_required(self) -> List[str]:
        """Returns a list of permission identifiers this plugin requires."""
        return []
