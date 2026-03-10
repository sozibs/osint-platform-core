"""Format conversion utilities: GeoJSON, STIX2, MISP, Neo4j, Elasticsearch."""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def to_geojson(location_entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a location entity dict to a GeoJSON Feature object."""
    lat = location_entity.get("latitude") or location_entity.get("lat")
    lng = location_entity.get("longitude") or location_entity.get("lng") or location_entity.get("lon")
    geometry = {"type": "Point", "coordinates": [lng, lat]} if lat is not None and lng is not None else None
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            k: v for k, v in location_entity.items()
            if k not in ("latitude", "longitude", "lat", "lng", "lon")
        },
    }


def from_stix2(stix_object: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a STIX 2.x object to a normalized entity dict."""
    stix_type = stix_object.get("type", "")
    _type_map = {
        "threat-actor": "person", "identity": "organization",
        "ipv4-addr": "ip", "ipv6-addr": "ip",
        "domain-name": "domain", "email-addr": "email",
        "url": "url", "file": "hash", "cryptocurrency-wallet": "cryptocurrency",
    }
    entity_type = _type_map.get(stix_type, "document")
    result: Dict[str, Any] = {
        "entity_type": entity_type,
        "name": (stix_object.get("name") or stix_object.get("value") or stix_object.get("id", "")),
        "aliases": stix_object.get("aliases", []),
        "attributes": {
            k: v for k, v in stix_object.items()
            if k not in ("type", "id", "name", "aliases", "spec_version")
        },
        "source_url": stix_object.get("external_references", [{}])[0].get("url") if stix_object.get("external_references") else None,
    }
    if stix_type in ("ipv4-addr", "ipv6-addr"):
        result["name"] = stix_object.get("value", "")
        result["attributes"]["ip_address"] = stix_object.get("value", "")
        result["attributes"]["ip_version"] = 6 if ":" in result["name"] else 4
    elif stix_type == "domain-name":
        result["name"] = stix_object.get("value", "")
        result["attributes"]["domain"] = stix_object.get("value", "")
    elif stix_type == "email-addr":
        result["name"] = stix_object.get("value", "")
        result["attributes"]["email_address"] = stix_object.get("value", "")
    elif stix_type == "file":
        hashes = stix_object.get("hashes", {})
        for htype in ("SHA-256", "SHA-1", "MD5"):
            if htype in hashes:
                result["name"] = hashes[htype]
                result["attributes"]["hash_value"] = hashes[htype]
                result["attributes"]["hash_type"] = htype.lower().replace("-", "")
                break
    return result


def to_stix2(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a normalized entity dict to a STIX 2.1 object."""
    import uuid as _uuid
    entity_type = entity.get("entity_type", "document")
    stix_id = f"unknown--{_uuid.uuid4()}"
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _stix_type_map = {
        "person": "threat-actor", "organization": "identity",
        "ip": "ipv4-addr", "domain": "domain-name",
        "email": "email-addr", "url": "url", "hash": "file",
        "cryptocurrency": "cryptocurrency-wallet",
        "location": "location", "document": "report",
    }
    stix_type = _stix_type_map.get(entity_type, "indicator")
    stix_id = f"{stix_type}--{_uuid.uuid4()}"
    base = {
        "type": stix_type, "id": stix_id,
        "spec_version": "2.1", "created": now, "modified": now,
    }
    if stix_type in ("ipv4-addr", "domain-name", "email-addr", "url", "cryptocurrency-wallet"):
        base["value"] = entity.get("name", "")
    else:
        base["name"] = entity.get("name", "")
    if entity.get("aliases"):
        base["aliases"] = entity["aliases"]
    return base


def to_misp_object(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a normalized entity to a MISP object template dict."""
    entity_type = entity.get("entity_type", "")
    _misp_templates = {
        "ip": "ip-port", "domain": "domain-ip", "email": "email",
        "url": "url", "hash": "file", "person": "person",
        "organization": "organization", "cryptocurrency": "cryptocurrency-transaction",
    }
    return {
        "name": _misp_templates.get(entity_type, "generic"),
        "meta-category": "osint",
        "description": f"OSINT {entity_type} entity",
        "attributes": [
            {"type": "text", "object_relation": k, "value": str(v)}
            for k, v in entity.get("attributes", {}).items()
            if v is not None
        ],
        "comment": entity.get("notes", ""),
    }


def from_csv_row(row: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Apply a field mapping to a CSV row dict."""
    return {mapping.get(k, k): v for k, v in row.items() if v}


def to_neo4j_format(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an entity to a Neo4j node-creation-compatible dict."""
    props = {
        "name": entity.get("name", ""),
        "entity_type": entity.get("entity_type", ""),
        "aliases": entity.get("aliases", []),
        "confidence": entity.get("confidence", 1.0),
    }
    props.update({k: v for k, v in entity.get("attributes", {}).items() if v is not None})
    return {"labels": [entity.get("entity_type", "Entity").capitalize()], "properties": props}


def to_elasticsearch_doc(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an entity to an Elasticsearch document dict."""
    doc = {
        "entity_type": entity.get("entity_type"),
        "name": entity.get("name"),
        "aliases": entity.get("aliases", []),
        "confidence": entity.get("confidence", 1.0),
        "source_url": entity.get("source_url"),
        "tags": entity.get("tags", []),
        "indexed_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    doc.update(entity.get("attributes", {}))
    return {k: v for k, v in doc.items() if v is not None}


def convert_coordinates(lat: float, lng: float, fmt: str = "decimal") -> str:
    """Convert decimal coordinates to various string formats."""
    if fmt == "decimal":
        return f"{lat:.6f},{lng:.6f}"
    if fmt == "dms":
        def to_dms(deg: float, pos: str, neg: str) -> str:
            direction = pos if deg >= 0 else neg
            deg = abs(deg)
            d = int(deg)
            m = int((deg - d) * 60)
            s = (deg - d - m / 60) * 3600
            return f"{d}°{m}'{s:.2f}\"{direction}"
        return f"{to_dms(lat, 'N', 'S')} {to_dms(lng, 'E', 'W')}"
    if fmt == "geohash":
        # Simplified geohash (not full implementation)
        return f"gh:{lat:.4f},{lng:.4f}"
    return f"{lat},{lng}"


def parse_cidr(cidr: str) -> Dict[str, Any]:
    """Parse a CIDR notation block and return network metadata."""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return {
            "cidr": str(network),
            "network_address": str(network.network_address),
            "broadcast_address": str(network.broadcast_address) if network.version == 4 else None,
            "netmask": str(network.netmask) if network.version == 4 else None,
            "prefix_length": network.prefixlen,
            "num_addresses": network.num_addresses,
            "version": network.version,
            "is_private": network.is_private,
            "is_global": network.is_global,
            "is_loopback": network.is_loopback,
        }
    except ValueError as exc:
        raise ValueError(f"Invalid CIDR notation: {cidr!r}") from exc
