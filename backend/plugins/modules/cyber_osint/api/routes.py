"""API routes for the Cyber OSINT module."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.routes.auth import get_current_user

from ..config import cyber_settings
from ..connectors.domain.cert_transparency import CertTransparency
from ..connectors.domain.dns_resolver import DnsResolver
from ..connectors.domain.subdomain_finder import SubdomainFinder
from ..connectors.domain.whois_client import WhoisClient
from ..connectors.email_security.dkim_checker import DkimChecker
from ..connectors.email_security.dmarc_checker import DmarcChecker
from ..connectors.email_security.spf_checker import SpfChecker
from ..connectors.ip.ip_lookup import IpLookup
from ..connectors.ssl.cert_analyzer import CertAnalyzer
from ..connectors.tech_detection.tech_detector import TechDetector
from ..connectors.threat_intel.abuse_ipdb import AbuseIpDb
from ..connectors.threat_intel.virustotal_client import VirusTotalClient
from .schemas import (
    CertificateAnalyzeRequest,
    CyberScanResponse,
    DomainLookupRequest,
    EmailSecurityRequest,
    IpLookupRequest,
    SubdomainScanRequest,
    ThreatIntelCheckRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _response(
    data: Optional[Dict[str, Any]],
    message: str,
    scan_status: str = "success",
) -> CyberScanResponse:
    return CyberScanResponse(
        scan_id=str(uuid.uuid4()),
        status=scan_status,
        data=data,
        message=message,
        scanned_at=datetime.now(timezone.utc),
    )


@router.post("/lookup/ip", response_model=CyberScanResponse)
async def lookup_ip(
    request: IpLookupRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Look up IP geolocation, abuse score, and threat intelligence in parallel."""
    ip_lookup = IpLookup()
    abuse_db = AbuseIpDb(api_key=cyber_settings.ABUSEIPDB_API_KEY)
    vt_client = VirusTotalClient(api_key=cyber_settings.VIRUSTOTAL_API_KEY)

    try:
        ip_record, abuse_data, vt_indicator = await asyncio.gather(
            ip_lookup.lookup(request.ip),
            abuse_db.check(request.ip),
            vt_client.check_ip(request.ip),
        )
    except Exception as exc:
        logger.error("IP lookup failed for %s: %s", request.ip, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IP lookup failed") from exc

    data: Dict[str, Any] = ip_record.model_dump()
    if abuse_data:
        data["abuse_confidence_score"] = abuse_data.get("abuseConfidenceScore", 0)
        data["abuse_total_reports"] = abuse_data.get("totalReports", 0)
    data["threat_intel"] = vt_indicator.model_dump()

    return _response(data, f"IP lookup completed for {request.ip}")


@router.post("/lookup/domain", response_model=CyberScanResponse)
async def lookup_domain(
    request: DomainLookupRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Perform WHOIS, DNS, certificate transparency, and tech detection in parallel."""
    whois = WhoisClient()
    dns = DnsResolver()
    ct = CertTransparency()
    tech = TechDetector()

    try:
        whois_data, dns_data, ct_domains, technologies = await asyncio.gather(
            whois.lookup(request.domain),
            dns.resolve(request.domain),
            ct.search(request.domain),
            tech.detect(f"https://{request.domain}"),
        )
    except Exception as exc:
        logger.error("Domain lookup failed for %s: %s", request.domain, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Domain lookup failed") from exc

    data: Dict[str, Any] = {
        "domain": request.domain,
        "whois": whois_data,
        "dns": dns_data,
        "cert_transparency_domains": ct_domains,
        "technologies": technologies,
    }
    return _response(data, f"Domain lookup completed for {request.domain}")


@router.post("/analyze/certificate", response_model=CyberScanResponse)
async def analyze_certificate(
    request: CertificateAnalyzeRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Fetch and analyze the SSL/TLS certificate for the given domain and port."""
    analyzer = CertAnalyzer()
    try:
        cert = await analyzer.analyze(request.domain, request.port)
    except Exception as exc:
        logger.error("Certificate analysis failed for %s:%d: %s", request.domain, request.port, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Certificate analysis failed") from exc

    return _response(cert.model_dump(), f"Certificate analyzed for {request.domain}:{request.port}")


@router.post("/scan/subdomain", response_model=CyberScanResponse)
async def scan_subdomains(
    request: SubdomainScanRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Find subdomains via DNS brute-force and certificate transparency logs."""
    finder = SubdomainFinder()
    ct = CertTransparency()

    try:
        dns_subdomains, ct_domains = await asyncio.gather(
            finder.find(request.domain),
            ct.search(request.domain),
        )
    except Exception as exc:
        logger.error("Subdomain scan failed for %s: %s", request.domain, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Subdomain scan failed") from exc

    combined = list({*dns_subdomains, *ct_domains})[: request.max_results]
    data: Dict[str, Any] = {
        "domain": request.domain,
        "subdomains": combined,
        "dns_found": dns_subdomains,
        "cert_transparency_found": ct_domains,
        "total": len(combined),
    }
    return _response(data, f"Subdomain scan completed for {request.domain}")


@router.post("/threat-intel/check", response_model=CyberScanResponse)
async def check_threat_intel(
    request: ThreatIntelCheckRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Check an indicator against VirusTotal based on its type."""
    vt_client = VirusTotalClient(api_key=cyber_settings.VIRUSTOTAL_API_KEY)
    try:
        if request.indicator_type == "ip":
            indicator = await vt_client.check_ip(request.indicator)
        else:
            indicator = await vt_client.check_domain(request.indicator)
    except Exception as exc:
        logger.error("Threat intel check failed for %s: %s", request.indicator, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Threat intel check failed") from exc

    return _response(indicator.model_dump(), f"Threat intel checked for {request.indicator}")


@router.get("/infrastructure/{entity_id}", response_model=CyberScanResponse)
async def get_infrastructure(
    entity_id: str,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Retrieve infrastructure mapping for a stored entity (not yet implemented)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Infrastructure retrieval for entity '{entity_id}' is not yet implemented.",
    )


@router.post("/email-security/analyze", response_model=CyberScanResponse)
async def analyze_email_security(
    request: EmailSecurityRequest,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Check SPF, DMARC, and DKIM records for a domain in parallel."""
    spf = SpfChecker()
    dmarc = DmarcChecker()
    dkim = DkimChecker()

    try:
        spf_result, dmarc_result, dkim_result = await asyncio.gather(
            spf.check(request.domain),
            dmarc.check(request.domain),
            dkim.check(request.domain),
        )
    except Exception as exc:
        logger.error("Email security analysis failed for %s: %s", request.domain, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email security analysis failed") from exc

    data: Dict[str, Any] = {
        "domain": request.domain,
        "spf": spf_result,
        "dmarc": dmarc_result,
        "dkim": dkim_result,
    }
    return _response(data, f"Email security analysis completed for {request.domain}")


@router.get("/vulnerabilities/{cve_id}", response_model=CyberScanResponse)
async def get_vulnerability(
    cve_id: str,
    _current_user: Any = Depends(get_current_user),
) -> CyberScanResponse:
    """Query the NVD CVE API for details about a specific CVE."""
    nvd_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(nvd_url, params={"cveId": cve_id})
            response.raise_for_status()
            nvd_data: Dict[str, Any] = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CVE '{cve_id}' not found") from exc
        logger.error("NVD API HTTP error for %s: %s", cve_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NVD API request failed") from exc
    except httpx.HTTPError as exc:
        logger.error("NVD API request failed for %s: %s", cve_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NVD API request failed") from exc
    except Exception as exc:
        logger.error("Unexpected error fetching CVE %s: %s", cve_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error") from exc

    vulnerabilities = nvd_data.get("vulnerabilities", [])
    if not vulnerabilities:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CVE '{cve_id}' not found")

    return _response({"cve_id": cve_id, "nvd_data": nvd_data}, f"CVE data retrieved for {cve_id}")
