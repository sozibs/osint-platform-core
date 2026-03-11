"""IP record model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class IpRecord(BaseModel):
    model_config = {"populate_by_name": True}

    ip: str
    ip_version: int = 4
    hostname: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    isp: Optional[str] = None
    org: Optional[str] = None
    asn: Optional[str] = None
    asn_name: Optional[str] = None
    is_proxy: bool = False
    is_tor: bool = False
    is_vpn: bool = False
    reputation_score: float = 0.0
    abuse_score: int = 0
    open_ports: List[int] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
