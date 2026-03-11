"""Workflow engine that routes investigation cases to the correct workflow."""

from __future__ import annotations

import logging
from datetime import datetime

from ..models.investigation_case import InvestigationCase
from .org_investigation import OrgInvestigation
from .person_investigation import PersonInvestigation

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Routes an :class:`InvestigationCase` to the appropriate workflow."""

    async def run_investigation(self, case: InvestigationCase) -> InvestigationCase:
        """Execute the workflow matching ``case.case_type`` and update *case*.

        Supported case types: ``"person"`` and ``"org"`` / ``"organization"``.
        Results are appended to ``case.evidence`` and ``case.status`` is updated.
        """
        logger.info(
            "WorkflowEngine: running '%s' investigation for case '%s'",
            case.case_type,
            case.id,
        )

        evidence_items = []

        if case.case_type == "person":
            workflow = PersonInvestigation()
            for target in case.targets:
                full_name = target.get("full_name") or target.get("name", "")
                if not full_name:
                    continue
                profile = await workflow.run(
                    full_name=full_name,
                    additional_context=target.get("context", {}),
                )
                evidence_items.append(
                    {"type": "person_profile", "data": profile.model_dump(mode="json")}
                )

        elif case.case_type in {"org", "organization"}:
            workflow_org = OrgInvestigation()
            for target in case.targets:
                org_name = target.get("name", "")
                jurisdiction = target.get("jurisdiction", "us")
                if not org_name:
                    continue
                profile = await workflow_org.run(
                    org_name=org_name, jurisdiction=jurisdiction
                )
                evidence_items.append(
                    {"type": "org_profile", "data": profile.model_dump(mode="json")}
                )

        else:
            logger.warning(
                "WorkflowEngine: unknown case_type '%s' for case '%s'",
                case.case_type,
                case.id,
            )

        case.evidence.extend(evidence_items)
        case.status = "completed" if evidence_items else "no_results"
        case.updated_at = datetime.utcnow()

        logger.info(
            "WorkflowEngine: case '%s' finished with status '%s'",
            case.id,
            case.status,
        )
        return case
