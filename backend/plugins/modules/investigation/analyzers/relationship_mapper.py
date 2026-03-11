"""Relationship mapper analyzer."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class RelationshipMapper:
    """Discovers relationships between profiles by finding shared attributes."""

    async def map(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a list of relationship dicts inferred from *profiles*.

        Identifies common employers, locations, and other shared entities
        across the supplied profiles and emits a relationship record for
        each match.
        """
        relationships: List[Dict[str, Any]] = []

        # Build lookup of attribute → list of profile indices
        employer_map: Dict[str, List[int]] = {}
        location_map: Dict[str, List[int]] = {}

        for idx, profile in enumerate(profiles):
            for job in profile.get("employment_history", []):
                employer = job.get("employer") or job.get("company")
                if employer:
                    employer_map.setdefault(employer, []).append(idx)

            for addr in profile.get("addresses", []):
                if addr:
                    location_map.setdefault(addr, []).append(idx)

        for employer, indices in employer_map.items():
            if len(indices) > 1:
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        relationships.append(
                            {
                                "type": "employment",
                                "shared_attribute": employer,
                                "profile_a_index": indices[i],
                                "profile_b_index": indices[j],
                            }
                        )

        for location, indices in location_map.items():
            if len(indices) > 1:
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        relationships.append(
                            {
                                "type": "association",
                                "shared_attribute": location,
                                "profile_a_index": indices[i],
                                "profile_b_index": indices[j],
                            }
                        )

        logger.debug(
            "RelationshipMapper: found %d relationships across %d profiles",
            len(relationships),
            len(profiles),
        )
        return relationships
