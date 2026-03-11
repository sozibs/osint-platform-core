"""Identity correlator: finds common attributes across a set of profiles."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_IDENTITY_FIELDS = ("username", "email", "display_name", "bio")


class IdentityCorrelator:
    async def correlate(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not profiles:
            return {"correlations": [], "summary": {"total_profiles": 0, "linked_identities": 0}}

        field_index: Dict[str, Dict[str, List[str]]] = {f: defaultdict(list) for f in _IDENTITY_FIELDS}

        for profile in profiles:
            platform = profile.get("platform", "unknown")
            for field in _IDENTITY_FIELDS:
                value = profile.get(field)
                if value and isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized:
                        field_index[field][normalized].append(platform)

        correlations: List[Dict[str, Any]] = []
        for field, value_map in field_index.items():
            for value, platforms in value_map.items():
                if len(platforms) > 1:
                    correlations.append(
                        {
                            "field": field,
                            "value": value,
                            "platforms": platforms,
                            "confidence": min(1.0, len(platforms) / max(1, len(profiles))),
                        }
                    )

        logger.debug(
            "Identity correlation: %d profiles → %d correlations",
            len(profiles),
            len(correlations),
        )

        return {
            "correlations": correlations,
            "summary": {
                "total_profiles": len(profiles),
                "linked_identities": len(correlations),
            },
        }
