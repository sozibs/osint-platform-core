"""Semantic similarity matching using rule-based attribute comparison."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Fields that uniquely identify entities by type
_UNIQUE_IDENTIFIERS: Dict[str, Set[str]] = {
    "email": {"email_address", "email"},
    "ip": {"ip_address", "ip"},
    "domain": {"domain", "fqdn"},
    "hash": {"hash_value", "hash"},
    "phone": {"phone_number", "phone"},
    "cryptocurrency": {"address", "wallet_address"},
}

# Compatible entity type pairs for cross-type matching
_COMPATIBLE_TYPES = {
    frozenset({"person", "organization"}),
    frozenset({"ip", "domain"}),
    frozenset({"email", "person"}),
    frozenset({"url", "domain"}),
}


class SemanticMatcher:
    """Rule-based semantic similarity matcher for OSINT entities."""

    def compare_entity_types(self, type1: str, type2: str) -> bool:
        """Return True if the two entity types are compatible for matching."""
        if type1 == type2:
            return True
        return frozenset({type1, type2}) in _COMPATIBLE_TYPES

    def match_by_unique_identifiers(
        self,
        e1: Dict[str, Any],
        e2: Dict[str, Any],
    ) -> Tuple[bool, float]:
        """Check for exact matches on unique identifier fields.

        Returns (matched, confidence):
        - Exact match on a unique identifier → 1.0 confidence
        - No unique identifier match → 0.0
        """
        entity_type = e1.get("entity_type", "")
        uid_fields = _UNIQUE_IDENTIFIERS.get(entity_type, set())

        for field in uid_fields:
            v1 = (e1.get(field) or e1.get("attributes", {}).get(field, ""))
            v2 = (e2.get(field) or e2.get("attributes", {}).get(field, ""))
            if v1 and v2:
                if str(v1).lower().strip() == str(v2).lower().strip():
                    return True, 1.0
                else:
                    return False, 0.0  # Same field, different value → definitely different

        # Alias overlap check (medium confidence)
        aliases1: set = set(a.lower() for a in (e1.get("aliases") or []))
        aliases2: set = set(a.lower() for a in (e2.get("aliases") or []))
        name1 = str(e1.get("name", "")).lower()
        name2 = str(e2.get("name", "")).lower()

        all1 = aliases1 | {name1}
        all2 = aliases2 | {name2}
        overlap = all1 & all2
        if overlap:
            return True, 0.7

        return False, 0.0

    def compute_attribute_overlap(
        self,
        e1_attrs: Dict[str, Any],
        e2_attrs: Dict[str, Any],
    ) -> float:
        """Compute Jaccard-style attribute value overlap between two attribute dicts."""
        if not e1_attrs or not e2_attrs:
            return 0.0
        common_keys = set(e1_attrs.keys()) & set(e2_attrs.keys())
        if not common_keys:
            return 0.0
        matching = sum(
            1
            for k in common_keys
            if e1_attrs[k] and e2_attrs[k]
            and str(e1_attrs[k]).lower().strip() == str(e2_attrs[k]).lower().strip()
        )
        return matching / len(common_keys)

    def compare_attributes(
        self,
        attrs1: Dict[str, Any],
        attrs2: Dict[str, Any],
    ) -> float:
        """Return a 0-1 similarity score based on attribute overlap."""
        return self.compute_attribute_overlap(attrs1, attrs2)

    def entity_similarity_score(
        self,
        e1: Dict[str, Any],
        e2: Dict[str, Any],
    ) -> float:
        """Comprehensive similarity score combining identifier, name, and attribute signals."""
        if not self.compare_entity_types(
            e1.get("entity_type", ""), e2.get("entity_type", "")
        ):
            return 0.0

        uid_match, uid_score = self.match_by_unique_identifiers(e1, e2)
        if uid_score >= 0.9:
            return uid_score

        from entity_resolution.matching.fuzzy_matcher import FuzzyMatcher
        fuzzy = FuzzyMatcher()
        name1 = str(e1.get("name", ""))
        name2 = str(e2.get("name", ""))
        name_score = fuzzy.combined_score(name1, name2) if name1 and name2 else 0.0

        attr_score = self.compute_attribute_overlap(
            e1.get("attributes", {}), e2.get("attributes", {})
        )

        # Weighted combination
        if uid_score > 0:
            return 0.5 * uid_score + 0.35 * name_score + 0.15 * attr_score
        return 0.6 * name_score + 0.4 * attr_score
