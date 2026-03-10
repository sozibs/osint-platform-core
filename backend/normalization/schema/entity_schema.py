"""Entity schemas for all supported OSINT entity types."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field


# ── Base entity schema ─────────────────────────────────────────────────────────

class EntitySchema(BaseModel):
    """Base schema shared by all entity types."""

    entity_type: str = Field(..., description="Canonical entity type string")
    name: str = Field(..., min_length=1, description="Primary identifier/display name")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_url: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None)

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


# ── Person ─────────────────────────────────────────────────────────────────────

class PersonSchema(EntitySchema):
    entity_type: str = "person"
    full_name: Optional[str] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    middle_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    birth_date: Optional[date] = Field(default=None)
    death_date: Optional[date] = Field(default=None)
    nationality: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 country code")
    occupation: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    email_addresses: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    social_media: Dict[str, str] = Field(
        default_factory=dict,
        description="Platform -> handle mapping, e.g. {'twitter': '@handle'}",
    )
    addresses: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    passport_number: Optional[str] = Field(default=None)
    national_id: Optional[str] = Field(default=None)


# ── Organization ───────────────────────────────────────────────────────────────

class OrganizationSchema(EntitySchema):
    entity_type: str = "organization"
    full_name: Optional[str] = Field(default=None)
    org_type: Optional[str] = Field(
        default=None,
        description="e.g. corporation, ngo, government, criminal_group",
    )
    registration_number: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2")
    founded_date: Optional[date] = Field(default=None)
    dissolved_date: Optional[date] = Field(default=None)
    website: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None)
    parent_organization: Optional[str] = Field(default=None)
    subsidiaries: List[str] = Field(default_factory=list)
    email_addresses: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    addresses: List[str] = Field(default_factory=list)


# ── Location ───────────────────────────────────────────────────────────────────

class LocationSchema(EntitySchema):
    entity_type: str = "location"
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    address: Optional[str] = Field(default=None)
    street: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state_province: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2")
    country_name: Optional[str] = Field(default=None)
    location_type: Optional[str] = Field(
        default=None, description="e.g. city, building, region, country"
    )
    geojson: Optional[Dict[str, Any]] = Field(default=None)


# ── IP Address ─────────────────────────────────────────────────────────────────

class IPAddressSchema(EntitySchema):
    entity_type: str = "ip"
    ip_address: str = Field(..., description="IPv4 or IPv6 address")
    ip_version: int = Field(default=4, description="4 or 6")
    asn: Optional[int] = Field(default=None, description="Autonomous System Number")
    asn_org: Optional[str] = Field(default=None)
    isp: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2")
    city: Optional[str] = Field(default=None)
    is_tor: bool = Field(default=False)
    is_vpn: bool = Field(default=False)
    is_proxy: bool = Field(default=False)
    is_datacenter: bool = Field(default=False)
    abuse_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    open_ports: List[int] = Field(default_factory=list)
    reverse_dns: Optional[str] = Field(default=None)


# ── Domain ─────────────────────────────────────────────────────────────────────

class DomainSchema(EntitySchema):
    entity_type: str = "domain"
    domain: str = Field(..., description="Fully qualified domain name")
    registrar: Optional[str] = Field(default=None)
    registrant: Optional[str] = Field(default=None)
    registered_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    nameservers: List[str] = Field(default_factory=list)
    mx_records: List[str] = Field(default_factory=list)
    ip_addresses: List[str] = Field(default_factory=list)
    whois_data: Optional[Dict[str, Any]] = Field(default=None)
    is_parked: bool = Field(default=False)
    is_expired: bool = Field(default=False)
    tld: Optional[str] = Field(default=None)


# ── Email ──────────────────────────────────────────────────────────────────────

class EmailSchema(EntitySchema):
    entity_type: str = "email"
    email_address: str = Field(..., description="Full email address")
    local_part: Optional[str] = Field(default=None, description="Part before @")
    domain: Optional[str] = Field(default=None, description="Part after @")
    is_disposable: bool = Field(default=False)
    is_role_based: bool = Field(default=False, description="e.g. admin@, support@")
    provider: Optional[str] = Field(default=None, description="e.g. gmail, outlook")
    breach_count: int = Field(default=0, ge=0)
    breaches: List[str] = Field(default_factory=list)


# ── Phone ──────────────────────────────────────────────────────────────────────

class PhoneSchema(EntitySchema):
    entity_type: str = "phone"
    phone_number: str = Field(..., description="Normalized E.164 format preferred")
    country_code: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2")
    country_dial_code: Optional[str] = Field(default=None, description="e.g. +1, +44")
    phone_type: Optional[str] = Field(
        default=None, description="mobile | landline | voip | fax | unknown"
    )
    carrier: Optional[str] = Field(default=None)
    is_valid: bool = Field(default=True)
    is_active: Optional[bool] = Field(default=None)


# ── URL ────────────────────────────────────────────────────────────────────────

class URLSchema(EntitySchema):
    entity_type: str = "url"
    url: str = Field(..., description="Full URL")
    scheme: Optional[str] = Field(default=None, description="http | https | ftp")
    domain: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    query_params: Optional[Dict[str, Any]] = Field(default=None)
    status_code: Optional[int] = Field(default=None)
    is_malicious: Optional[bool] = Field(default=None)
    redirect_chain: List[str] = Field(default_factory=list)
    final_url: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)


# ── Hash ───────────────────────────────────────────────────────────────────────

class HashSchema(EntitySchema):
    entity_type: str = "hash"
    hash_value: str = Field(..., description="Hex-encoded hash digest")
    hash_type: str = Field(
        ..., description="md5 | sha1 | sha256 | sha512 | ssdeep | tlsh"
    )
    file_name: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None, ge=0, description="Bytes")
    file_type: Optional[str] = Field(default=None, description="MIME type")
    is_malicious: Optional[bool] = Field(default=None)
    malware_family: Optional[str] = Field(default=None)
    first_seen: Optional[datetime] = Field(default=None)
    last_seen: Optional[datetime] = Field(default=None)


# ── Cryptocurrency ─────────────────────────────────────────────────────────────

class CryptocurrencySchema(EntitySchema):
    entity_type: str = "cryptocurrency"
    address: str = Field(..., description="Blockchain wallet address")
    currency_type: str = Field(
        ..., description="bitcoin | ethereum | monero | litecoin | etc."
    )
    blockchain: Optional[str] = Field(default=None, description="Network name")
    balance: Optional[float] = Field(default=None, ge=0.0)
    transaction_count: Optional[int] = Field(default=None, ge=0)
    first_seen: Optional[datetime] = Field(default=None)
    last_seen: Optional[datetime] = Field(default=None)
    is_exchange: bool = Field(default=False)
    is_mixer: bool = Field(default=False)
    cluster_id: Optional[str] = Field(default=None)


# ── Vehicle ────────────────────────────────────────────────────────────────────

class VehicleSchema(EntitySchema):
    entity_type: str = "vehicle"
    license_plate: Optional[str] = Field(default=None)
    vin: Optional[str] = Field(default=None, description="Vehicle Identification Number")
    make: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    year: Optional[int] = Field(default=None, ge=1885, le=2100)
    color: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2")
    registration_country: Optional[str] = Field(default=None)


# ── Document ───────────────────────────────────────────────────────────────────

class DocumentSchema(EntitySchema):
    entity_type: str = "document"
    title: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    document_type: Optional[str] = Field(
        default=None, description="pdf | docx | txt | html | spreadsheet | etc."
    )
    author: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    modified_at: Optional[datetime] = Field(default=None)
    file_hash: Optional[str] = Field(default=None, description="SHA-256 of the file")
    file_size: Optional[int] = Field(default=None, ge=0)
    url: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    page_count: Optional[int] = Field(default=None, ge=0)


# ── Registry ───────────────────────────────────────────────────────────────────

class EntityTypeRegistry:
    """Maps entity_type strings to their schema classes."""

    _registry: ClassVar[Dict[str, Type[EntitySchema]]] = {
        "person": PersonSchema,
        "organization": OrganizationSchema,
        "location": LocationSchema,
        "ip": IPAddressSchema,
        "domain": DomainSchema,
        "email": EmailSchema,
        "phone": PhoneSchema,
        "url": URLSchema,
        "hash": HashSchema,
        "cryptocurrency": CryptocurrencySchema,
        "vehicle": VehicleSchema,
        "document": DocumentSchema,
    }

    @classmethod
    def get_schema_class(cls, entity_type: str) -> Type[EntitySchema]:
        """Return the schema class for a given entity type.

        Raises KeyError if the type is not registered.
        """
        if entity_type not in cls._registry:
            raise KeyError(
                f"Unknown entity type: {entity_type!r}. "
                f"Valid types: {sorted(cls._registry)}"
            )
        return cls._registry[entity_type]

    @classmethod
    def validate(cls, entity_type: str, data: Dict[str, Any]) -> EntitySchema:
        """Validate and parse *data* into the appropriate schema instance."""
        schema_cls = cls.get_schema_class(entity_type)
        return schema_cls(**data)

    @classmethod
    def supported_types(cls) -> List[str]:
        """Return a sorted list of all supported entity type strings."""
        return sorted(cls._registry.keys())

    @classmethod
    def register(cls, entity_type: str, schema_cls: Type[EntitySchema]) -> None:
        """Dynamically register a new entity type schema (for plugins)."""
        cls._registry[entity_type] = schema_cls
