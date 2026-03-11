from __future__ import annotations

import logging
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.interfaces.plugin_interface import PluginInterface

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry that tracks all loaded plugins."""

    _instance: Optional["PluginRegistry"] = None

    @classmethod
    def get_instance(cls) -> "PluginRegistry":
        """Return the singleton PluginRegistry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __new__(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
        return cls._instance

    def __init__(self) -> None:
        # _plugins is set once in __new__; guard against repeated __init__ calls.
        if hasattr(self, "_plugins"):
            return
        self._plugins: Dict[str, "PluginInterface"] = {}

    def register(self, plugin: "PluginInterface") -> None:
        """Register a plugin by its name."""
        self._plugins[plugin.name] = plugin
        logger.info("Plugin registered: %s v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry by name."""
        self._plugins.pop(name, None)

    def get(self, name: str) -> Optional["PluginInterface"]:
        """Return the plugin with the given name, or None if not found."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """Return a list of registered plugin names."""
        return list(self._plugins.keys())

    def list_all(self) -> List["PluginInterface"]:
        """Return a list of all registered plugin instances."""
        return list(self._plugins.values())


registry = PluginRegistry.get_instance()
