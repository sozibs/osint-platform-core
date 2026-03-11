from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from plugins.registry import registry

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def load_all_plugins(app: "FastAPI") -> None:
    """Discover, initialize, and register all built-in module plugins."""
    plugin_classes = []

    try:
        from plugins.modules.digital_footprint.plugin import DigitalFootprintPlugin
        plugin_classes.append(DigitalFootprintPlugin)
    except Exception:
        logger.error("Failed to load DigitalFootprintPlugin", exc_info=True)

    try:
        from plugins.modules.investigation.plugin import InvestigationPlugin
        plugin_classes.append(InvestigationPlugin)
    except Exception:
        logger.error("Failed to load InvestigationPlugin", exc_info=True)

    try:
        from plugins.modules.cyber_osint.plugin import CyberOsintPlugin
        plugin_classes.append(CyberOsintPlugin)
    except Exception:
        logger.error("Failed to load CyberOsintPlugin", exc_info=True)

    try:
        from plugins.modules.misinformation.plugin import MisinformationPlugin
        plugin_classes.append(MisinformationPlugin)
    except Exception:
        logger.error("Failed to load MisinformationPlugin", exc_info=True)

    for plugin_cls in plugin_classes:
        try:
            plugin = plugin_cls()
            plugin.initialize()
            plugin.register_routes(app)
            registry.register(plugin)
            logger.info("Loaded plugin: %s v%s", plugin.name, plugin.version)
        except Exception:
            logger.error("Failed to initialize plugin %s", plugin_cls.__name__, exc_info=True)
