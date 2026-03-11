"""API routes for the Investigation module."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.routes.auth import get_current_user

from ..connectors.public_records.business_records import BusinessRecordsConnector
from ..connectors.public_records.court_records import CourtRecordsConnector
from ..models.investigation_case import InvestigationCase
from ..workflows.org_investigation import OrgInvestigation
from ..workflows.person_investigation import PersonInvestigation
from ..workflows.workflow_engine import WorkflowEngine
from .schemas import (
    CaseCreateRequest,
    InvestigationResponse,
    OrgSearchRequest,
    PersonSearchRequest,
    PublicRecordSearchRequest,
    ReportGenerateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _response(
    data: Any | None,
    message: str,
    inv_status: str = "success",
    response_id: str | None = None,
) -> InvestigationResponse:
    return InvestigationResponse(
        id=response_id or str(uuid.uuid4()),
        status=inv_status,
        data=data if isinstance(data, dict) else (data if data is None else {"result": data}),
        message=message,
        timestamp=datetime.now(timezone.utc),
    )


# ── Cases ─────────────────────────────────────────────────────────────────────

@router.post("/cases", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreateRequest,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Create a new investigation case and run the appropriate workflow."""
    case = InvestigationCase(
        title=body.title,
        description=body.description,
        case_type=body.case_type,
        targets=body.targets,
    )
    try:
        engine = WorkflowEngine()
        case = await engine.run_investigation(case)
    except Exception as exc:
        logger.exception("create_case: workflow error for case '%s': %s", case.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation workflow failed: {exc}",
        ) from exc

    return _response(
        data=case.model_dump(mode="json"),
        message=f"Case '{case.title}' created and investigation completed.",
        inv_status=case.status,
        response_id=case.id,
    )


@router.get("/cases/{case_id}", response_model=InvestigationResponse)
async def get_case(
    case_id: str,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Retrieve a saved investigation case by ID."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Case retrieval is not yet implemented. Results are returned inline at creation time.",
    )


# ── Person / Org search ───────────────────────────────────────────────────────

@router.post("/search/person", response_model=InvestigationResponse)
async def search_person(
    body: PersonSearchRequest,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Run a person investigation and return the resulting profile."""
    try:
        workflow = PersonInvestigation()
        profile = await workflow.run(
            full_name=body.full_name,
            additional_context=body.additional_context,
        )
    except Exception as exc:
        logger.exception("search_person: error for '%s': %s", body.full_name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Person investigation failed: {exc}",
        ) from exc

    return _response(
        data=profile.model_dump(mode="json"),
        message=f"Person investigation completed for '{body.full_name}'.",
    )


@router.post("/search/organization", response_model=InvestigationResponse)
async def search_organization(
    body: OrgSearchRequest,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Run an organization investigation and return the resulting profile."""
    try:
        workflow = OrgInvestigation()
        profile = await workflow.run(
            org_name=body.name,
            jurisdiction=body.jurisdiction,
        )
    except Exception as exc:
        logger.exception("search_organization: error for '%s': %s", body.name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"organization investigation failed: {exc}",
        ) from exc

    return _response(
        data=profile.model_dump(mode="json"),
        message=f"organization investigation completed for '{body.name}'.",
    )


# ── Public records ────────────────────────────────────────────────────────────

@router.post("/public-records/search", response_model=InvestigationResponse)
async def search_public_records(
    body: PublicRecordSearchRequest,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Search public records using court or business record connectors."""
    try:
        records: List[Dict[str, Any]] = []

        record_type = (body.record_type or "").lower()
        if record_type in {"court", ""}:
            court = CourtRecordsConnector()
            court_results = await court.search(
                query=body.query,
                jurisdiction=body.jurisdiction or "federal",
            )
            records.extend(r.model_dump(mode="json") for r in court_results)

        if record_type in {"business", "sec", ""}:
            biz = BusinessRecordsConnector()
            biz_results = await biz.search(company_name=body.query)
            records.extend(r.model_dump(mode="json") for r in biz_results)

    except Exception as exc:
        logger.exception("search_public_records: error for '%s': %s", body.query, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Public records search failed: {exc}",
        ) from exc

    return _response(
        data={"records": records, "total": len(records)},
        message=f"Public records search completed for '{body.query}'. {len(records)} result(s) found.",
    )


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/timeline/{entity_id}", response_model=InvestigationResponse)
async def get_timeline(
    entity_id: str,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Return the timeline for a saved entity."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Timeline retrieval is not yet implemented. Use the TimelineBuilder analyzer directly.",
    )


# ── Reports ───────────────────────────────────────────────────────────────────

@router.post("/reports/generate", response_model=InvestigationResponse)
async def generate_report(
    body: ReportGenerateRequest,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Generate an investigation report for a case."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Report generation is not yet implemented.",
    )


# ── Relationships ─────────────────────────────────────────────────────────────

@router.get("/relationships/{entity_id}", response_model=InvestigationResponse)
async def get_relationships(
    entity_id: str,
    _current_user=Depends(get_current_user),
) -> InvestigationResponse:
    """Return the relationship map for a saved entity."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Relationship map retrieval is not yet implemented. Use the RelationshipMapper analyzer directly.",
    )
