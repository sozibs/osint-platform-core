"""Maps raw data fields to normalized entity fields."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Common field name synonyms ─────────────────────────────────────────────────

# Maps canonical field names → list of common aliases found in source data
_COMMON_SYNONYMS: Dict[str, List[str]] = {
    # Person
    "full_name": ["name", "full_name", "person_name", "display_name", "fullname"],
    "first_name": ["first_name", "firstname", "given_name", "forename", "fname"],
    "last_name": ["last_name", "lastname", "family_name", "surname", "lname"],
    "birth_date": ["birth_date", "dob", "date_of_birth", "birthday", "born"],
    "nationality": ["nationality", "citizenship", "country_of_birth"],
    "occupation": ["occupation", "job", "profession", "title", "role"],
    # Organization
    "org_type": ["org_type", "type", "organization_type", "company_type", "category"],
    "registration_number": ["registration_number", "reg_no", "company_no", "ein", "tax_id"],
    "founded_date": ["founded_date", "founded", "established", "inception_date"],
    "industry": ["industry", "sector", "business_type"],
    # Location
    "latitude": ["latitude", "lat", "y"],
    "longitude": ["longitude", "lon", "lng", "long", "x"],
    "city": ["city", "municipality", "town", "locality"],
    "state_province": ["state", "province", "region", "state_province"],
    "postal_code": ["postal_code", "zip", "zipcode", "postcode"],
    "country": ["country", "country_code", "nation"],
    # IP
    "ip_address": ["ip", "ip_address", "ipaddr", "address", "src_ip", "dst_ip", "value"],
    "asn": ["asn", "as_number", "autonomous_system"],
    "isp": ["isp", "provider", "operator"],
    # Domain
    "domain": ["domain", "fqdn", "hostname", "host", "value"],
    "registrar": ["registrar", "domain_registrar"],
    "registered_at": ["registered_at", "created", "creation_date", "register_date"],
    "expires_at": ["expires_at", "expiry", "expiration_date", "expiry_date"],
    # Email
    "email_address": ["email", "email_address", "mail", "e_mail", "value"],
    # Phone
    "phone_number": ["phone", "phone_number", "telephone", "tel", "mobile", "value"],
    "carrier": ["carrier", "operator", "network"],
    # Hash
    "hash_value": ["hash", "hash_value", "digest", "checksum", "md5", "sha1", "sha256", "value"],
    "hash_type": ["hash_type", "algorithm", "type"],
    # Crypto
    "address": ["address", "wallet", "wallet_address", "account", "value"],
    "currency_type": ["currency", "coin", "type", "blockchain"],
    # Common
    "url": ["url", "link", "href", "source_url", "web_url"],
    "name": ["name", "title", "label", "value"],
}

# Inverted index: alias → canonical field name
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _aliases in _COMMON_SYNONYMS.items():
    for _alias in _aliases:
        if _alias not in _ALIAS_TO_CANONICAL:
            _ALIAS_TO_CANONICAL[_alias] = _canonical


class FieldMapper:
    """Maps raw data field names to normalized entity field names."""

    # ── Core mapping ───────────────────────────────────────────────────────────

    def apply_mapping(
        self,
        raw_data: Dict[str, Any],
        mapping_config: Dict[str, str],
    ) -> Dict[str, Any]:
        """Apply an explicit field mapping to *raw_data*.

        *mapping_config* format: ``{source_field: target_field}``.
        Dot-notation paths are supported for both source and target.
        Unmapped fields are preserved.
        """
        result: Dict[str, Any] = {}

        # Start with all source fields, then overlay mapped versions
        for src_key, value in raw_data.items():
            canonical = mapping_config.get(src_key, src_key)
            if canonical:
                self._set_nested(result, canonical, value)

        # Handle dot-notation source paths
        for src_path, dst_field in mapping_config.items():
            if "." in src_path:
                value = self._get_nested(raw_data, src_path)
                if value is not None and dst_field:
                    self._set_nested(result, dst_field, value)

        return result

    # ── Auto detection ─────────────────────────────────────────────────────────

    def auto_detect_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Heuristically rename known alias fields to canonical names.

        Fields that already use canonical names are left unchanged.
        Unknown fields are preserved as-is.
        """
        result: Dict[str, Any] = {}
        for key, value in raw_data.items():
            canonical = _ALIAS_TO_CANONICAL.get(key.lower(), key)
            if canonical in result:
                # Don't overwrite already-mapped canonical fields
                if key not in result:
                    result[key] = value
            else:
                result[canonical] = value
        return result

    # ── Mapping utilities ──────────────────────────────────────────────────────

    def merge_mappings(
        self, base: Dict[str, str], override: Dict[str, str]
    ) -> Dict[str, str]:
        """Merge two mapping dicts, with *override* taking precedence."""
        merged = dict(base)
        merged.update(override)
        return merged

    def validate_mapping(
        self, mapping: Dict[str, str], entity_type: str
    ) -> List[str]:
        """Validate a field mapping against the known schema for *entity_type*.

        Returns a list of warning strings (empty = no issues found).
        """
        from normalization.schema.entity_schema import EntityTypeRegistry

        errors: List[str] = []
        try:
            schema_cls = EntityTypeRegistry.get_schema_class(entity_type)
        except KeyError:
            errors.append(f"Unknown entity type: {entity_type!r}")
            return errors

        schema_fields = set(schema_cls.model_fields.keys())
        for src, dst in mapping.items():
            if dst and dst not in schema_fields:
                errors.append(
                    f"Mapping target field {dst!r} is not a known field of "
                    f"{entity_type!r} schema."
                )
        return errors

    # ── Nested path helpers ────────────────────────────────────────────────────

    @staticmethod
    def _get_nested(data: Dict[str, Any], path: str) -> Any:
        """Retrieve a value from a nested dict using dot-separated *path*."""
        obj: Any = data
        for part in path.split("."):
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj

    @staticmethod
    def _set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value in a nested dict using dot-separated *path*."""
        parts = path.split(".")
        obj: Any = data
        for part in parts[:-1]:
            if part not in obj or not isinstance(obj[part], dict):
                obj[part] = {}
            obj = obj[part]
        obj[parts[-1]] = value
