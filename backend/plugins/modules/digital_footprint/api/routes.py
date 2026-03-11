"""API routes for the Digital Footprint module."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.routes.auth import get_current_user

from ..config import df_settings
from ..connectors.domain.dns_analyzer import DnsAnalyzer
from ..connectors.domain.whois_lookup import WhoisLookup
from ..connectors.email.breach_checker import BreachChecker
from ..connectors.email.email_validator import EmailValidator
from ..connectors.phone.number_validator import NumberValidator
from ..connectors.social_media.github_connector import GitHubConnector
from ..connectors.social_media.linkedin_connector import LinkedInConnector
from ..connectors.social_media.reddit_connector import RedditConnector
from ..connectors.social_media.twitter_connector import TwitterConnector
from ..connectors.username.username_checker import UsernameChecker
from .schemas import (
    DomainScanRequest,
    EmailScanRequest,
    PhoneScanRequest,
    ScanResponse,
    SocialMediaScanRequest,
    UsernameScanRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _scan_response(
    data: Optional[Dict[str, Any]],
    message: str,
    status_str: str = "success",
) -> ScanResponse:
    return ScanResponse(
        scan_id=str(uuid.uuid4()),
        status=status_str,
        data=data,
        message=message,
        scanned_at=datetime.now(timezone.utc),
    )


@router.post("/scan/email", response_model=ScanResponse)
async def scan_email(
    request: EmailScanRequest,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    validator = EmailValidator()
    checker = BreachChecker(api_key=df_settings.HAVEIBEENPWNED_API_KEY)

    record = await validator.validate(str(request.email))
    breaches = await checker.check(str(request.email))

    record.breaches = breaches
    record.breach_count = len(breaches)

    return _scan_response(
        data=record.model_dump(mode="json"),
        message=f"Email scan completed for {request.email}",
    )


@router.post("/scan/phone", response_model=ScanResponse)
async def scan_phone(
    request: PhoneScanRequest,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    validator = NumberValidator()
    record = await validator.validate(request.phone)

    return _scan_response(
        data=record.model_dump(mode="json"),
        message=f"Phone scan completed for {request.phone}",
    )


@router.post("/scan/username", response_model=ScanResponse)
async def scan_username(
    request: UsernameScanRequest,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    checker = UsernameChecker()
    record = await checker.check(request.username)

    return _scan_response(
        data=record.model_dump(mode="json"),
        message=f"Username scan completed for {request.username}",
    )


@router.post("/scan/domain", response_model=ScanResponse)
async def scan_domain(
    request: DomainScanRequest,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    whois = WhoisLookup()
    dns = DnsAnalyzer()

    domain_record = await whois.lookup(request.domain)
    dns_records = await dns.analyze(request.domain)
    domain_record.dns_records = dns_records

    return _scan_response(
        data=domain_record.model_dump(mode="json"),
        message=f"Domain scan completed for {request.domain}",
    )


@router.post("/scan/social-media", response_model=ScanResponse)
async def scan_social_media(
    request: SocialMediaScanRequest,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    platform = request.platform.lower()
    profile = None

    if platform == "twitter":
        connector = TwitterConnector(
            api_key=df_settings.TWITTER_API_KEY,
            api_secret=df_settings.TWITTER_API_SECRET,
        )
        profile = await connector.lookup_profile(request.username)
    elif platform == "github":
        connector = GitHubConnector(token=df_settings.GITHUB_TOKEN)
        profile = await connector.lookup_profile(request.username)
    elif platform == "reddit":
        connector = RedditConnector(
            client_id=df_settings.REDDIT_CLIENT_ID,
            client_secret=df_settings.REDDIT_CLIENT_SECRET,
        )
        profile = await connector.lookup_profile(request.username)
    elif platform == "linkedin":
        connector = LinkedInConnector()
        profile = await connector.lookup_profile(request.username)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: '{platform}'. Supported: twitter, github, reddit, linkedin.",
        )

    if profile is None:
        return _scan_response(
            data=None,
            message=f"No profile found for '{request.username}' on {platform}",
            status_str="not_found",
        )

    return _scan_response(
        data=profile.model_dump(mode="json"),
        message=f"Social media scan completed for {request.username} on {platform}",
    )


@router.get("/profiles/{scan_id}", response_model=ScanResponse)
async def get_profile(
    scan_id: str,
    _current_user=Depends(get_current_user),
) -> ScanResponse:
    # Scan result persistence is not yet implemented.
    # This endpoint is reserved for a future storage layer (e.g. Redis / PostgreSQL).
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Scan result retrieval is not yet implemented. Results are returned inline at scan time.",
    )
