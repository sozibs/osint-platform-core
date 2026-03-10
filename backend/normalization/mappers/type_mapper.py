"""Maps raw type strings to canonical OSINT entity types."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from normalization.schema.validation_schema import (
    EMAIL_PATTERN, IPV4_PATTERN, IPV6_PATTERN, DOMAIN_PATTERN,
    MD5_PATTERN, SHA1_PATTERN, SHA256_PATTERN, SHA512_PATTERN,
)

_TYPE_SYNONYMS: Dict[str, str] = {
    "person": "person", "people": "person", "individual": "person", "human": "person",
    "suspect": "person", "target": "person", "subject": "person",
    "organization": "organization", "org": "organization", "company": "organization",
    "corporation": "organization", "business": "organization", "group": "organization",
    "location": "location", "place": "location", "address": "location", "geo": "location",
    "ip": "ip", "ip_address": "ip", "ipv4": "ip", "ipv6": "ip", "host": "ip",
    "domain": "domain", "fqdn": "domain", "hostname": "domain", "website": "domain",
    "email": "email", "email_address": "email", "mail": "email",
    "phone": "phone", "phone_number": "phone", "telephone": "phone", "mobile": "phone",
    "url": "url", "link": "url", "uri": "url", "webpage": "url",
    "hash": "hash", "md5": "hash", "sha1": "hash", "sha256": "hash", "sha512": "hash",
    "cryptocurrency": "cryptocurrency", "crypto": "cryptocurrency", "wallet": "cryptocurrency",
    "bitcoin": "cryptocurrency", "ethereum": "cryptocurrency",
    "vehicle": "vehicle", "car": "vehicle", "license_plate": "vehicle",
    "document": "document", "file": "document", "report": "document",
}

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_BTC_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
_ETH_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_PHONE_RE = re.compile(r"^\+?[\d\s\-().]{7,20}$")
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.IGNORECASE)
_PLATE_RE = re.compile(r"^[A-Z0-9\-\s]{4,10}$", re.IGNORECASE)


class EntityTypeMapper:
    """Classifies raw data records into canonical entity types."""

    def classify_entity(self, data: Dict[str, Any]) -> str:
        """Determine the entity type for *data* using heuristics.

        Checks explicit ``type`` fields first, then falls back to
        value-based pattern matching.
        """
        # Explicit type hint
        for key in ("type", "entity_type", "kind", "category", "record_type"):
            raw_type = data.get(key, "")
            if raw_type and isinstance(raw_type, str):
                canonical = _TYPE_SYNONYMS.get(raw_type.lower().strip())
                if canonical:
                    return canonical

        # Value heuristics
        scores: Dict[str, float] = {}
        for entity_type in (
            "ip", "email", "url", "domain", "hash",
            "cryptocurrency", "phone", "person",
            "organization", "location", "vehicle", "document",
        ):
            scores[entity_type] = self.type_confidence_score(data, entity_type)

        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0.3 else "document"

    def type_confidence_score(self, data: Dict[str, Any], entity_type: str) -> float:
        """Return a 0-1 confidence that *data* represents *entity_type*."""
        all_values = [str(v) for v in data.values() if v and isinstance(v, str)]
        field_names = {k.lower() for k in data.keys()}
        primary = all_values[0] if all_values else ""

        if entity_type == "ip":
            score = 0.0
            if field_names & {"ip", "ip_address", "ipaddr"}:
                score += 0.7
            if primary and (IPV4_PATTERN.match(primary) or IPV6_PATTERN.match(primary)):
                score += 0.3
            return min(score, 1.0)

        if entity_type == "email":
            score = 0.0
            if field_names & {"email", "email_address", "mail"}:
                score += 0.7
            if primary and EMAIL_PATTERN.match(primary):
                score += 0.3
            return min(score, 1.0)

        if entity_type == "url":
            score = 0.0
            if field_names & {"url", "link", "href", "uri"}:
                score += 0.6
            if primary and _URL_RE.match(primary):
                score += 0.4
            return min(score, 1.0)

        if entity_type == "domain":
            score = 0.0
            if field_names & {"domain", "fqdn", "hostname"}:
                score += 0.7
            if primary and DOMAIN_PATTERN.match(primary) and "." in primary:
                score += 0.3
            return min(score, 1.0)

        if entity_type == "hash":
            score = 0.0
            if field_names & {"hash", "md5", "sha1", "sha256", "sha512", "checksum"}:
                score += 0.6
            for val in all_values:
                if any(p.match(val) for p in (MD5_PATTERN, SHA1_PATTERN, SHA256_PATTERN, SHA512_PATTERN)):
                    score += 0.4
                    break
            return min(score, 1.0)

        if entity_type == "cryptocurrency":
            score = 0.0
            if field_names & {"wallet", "address", "cryptocurrency", "crypto"}:
                score += 0.5
            for val in all_values:
                if _BTC_RE.match(val) or _ETH_RE.match(val):
                    score += 0.5
                    break
            return min(score, 1.0)

        if entity_type == "phone":
            score = 0.0
            if field_names & {"phone", "telephone", "mobile", "tel"}:
                score += 0.7
            if primary and _PHONE_RE.match(primary):
                score += 0.3
            return min(score, 1.0)

        if entity_type == "person":
            score = 0.0
            person_fields = {"name", "first_name", "last_name", "full_name", "person_name",
                             "birth_date", "dob", "nationality", "occupation", "gender"}
            overlap = field_names & person_fields
            score += min(len(overlap) * 0.2, 0.8)
            return min(score, 1.0)

        if entity_type == "organization":
            org_fields = {"org", "company", "organization", "registration_number",
                          "industry", "founded", "website"}
            overlap = field_names & org_fields
            return min(len(overlap) * 0.25, 1.0)

        if entity_type == "location":
            loc_fields = {"latitude", "longitude", "lat", "lng", "city",
                          "country", "address", "postal_code", "coordinates"}
            overlap = field_names & loc_fields
            return min(len(overlap) * 0.25, 1.0)

        if entity_type == "vehicle":
            veh_fields = {"vin", "plate", "license_plate", "make", "model", "vehicle"}
            overlap = field_names & veh_fields
            return min(len(overlap) * 0.35, 1.0)

        if entity_type == "document":
            doc_fields = {"title", "content", "author", "document_type", "page_count"}
            overlap = field_names & doc_fields
            return min(len(overlap) * 0.25, 1.0)

        return 0.0
