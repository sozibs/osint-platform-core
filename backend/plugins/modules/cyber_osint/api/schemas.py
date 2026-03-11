"""Pydantic request and response schemas for the Cyber OSINT API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class IpLookupRequest(BaseModel):
    ip: str = Field(
        ...,
        pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^[0-9a-fA-F:]+$",
        description="IPv4 or IPv6 address to look up.",
    )


class DomainLookupRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253, description="Domain name to investigate.")


class CertificateAnalyzeRequest(BaseModel):
    domain: str = Field(..., description="Domain to retrieve the SSL certificate from.")
    port: int = Field(443, description="TCP port to connect to.")


class SubdomainScanRequest(BaseModel):
    domain: str = Field(..., description="Root domain to enumerate subdomains for.")
    max_results: int = Field(50, description="Maximum number of subdomains to return.")


class ThreatIntelCheckRequest(BaseModel):
    indicator: str = Field(..., description="The indicator value to check (IP, domain, URL, or hash).")
    indicator_type: str = Field(
        ...,
        pattern="^(ip|domain|url|hash)$",
        description="The type of the indicator.",
    )


class EmailSecurityRequest(BaseModel):
    domain: str = Field(..., description="Domain to check email security records for.")


class CyberScanResponse(BaseModel):
    scan_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    message: str
    scanned_at: datetime
