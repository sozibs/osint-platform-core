"""
Export router.

Generates downloadable reports from cases and entities in multiple formats:
JSON, CSV, XLSX, PDF.  PDF generation uses WeasyPrint when available.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Case, CaseEntity, Entity, Relationship, User
from storage.database.postgres.queries import get_all, get_by_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export")

EXPORT_FORMATS = {"json", "csv", "xlsx", "pdf"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    resource_type: str = Field(..., description="entities | case | relationships")
    resource_ids: Optional[List[uuid.UUID]] = None
    format: str = Field(default="json", description="json | csv | xlsx | pdf")
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_relationships: bool = False


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _entity_to_dict(e: Entity) -> Dict[str, Any]:
    return {
        "id": str(e.id),
        "entity_type": e.entity_type,
        "name": e.name,
        "aliases": e.aliases or [],
        "confidence_score": e.confidence_score,
        "is_canonical": e.is_canonical,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "attributes": e.attributes or {},
    }


def _relationship_to_dict(r: Relationship) -> Dict[str, Any]:
    return {
        "id": str(r.id),
        "source_entity_id": str(r.source_entity_id),
        "target_entity_id": str(r.target_entity_id),
        "relationship_type": r.relationship_type,
        "confidence_score": r.confidence_score,
        "is_directed": r.is_directed,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "attributes": r.attributes or {},
    }


def _case_to_dict(c: Case) -> Dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "status": c.status,
        "priority": c.priority,
        "tags": c.tags or [],
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "created_by": str(c.created_by),
        "assigned_to": str(c.assigned_to) if c.assigned_to else None,
    }


# ── Format generators ─────────────────────────────────────────────────────────

def _to_json(records: List[Dict[str, Any]]) -> bytes:
    return json.dumps(records, indent=2, default=str).encode("utf-8")


def _to_csv(records: List[Dict[str, Any]]) -> bytes:
    if not records:
        return b""
    output = io.StringIO()
    # Flatten top-level keys; nested dicts become JSON strings
    fieldnames = list(records[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in records:
        flat = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else v
            for k, v in row.items()
        }
        writer.writerow(flat)
    return output.getvalue().encode("utf-8")


def _to_xlsx(records: List[Dict[str, Any]], sheet_name: str = "Data") -> bytes:
    try:
        import pandas as pd
        from openpyxl import Workbook

        df = pd.DataFrame(records)
        # Serialise complex types to strings
        for col in df.columns:
            df[col] = df[col].apply(
                lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v
            )
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        return buf.getvalue()
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="pandas / openpyxl not installed; XLSX export unavailable",
        ) from exc


def _to_pdf(records: List[Dict[str, Any]], title: str = "OSINT Report") -> bytes:
    try:
        from weasyprint import HTML

        rows_html = "".join(
            f"<tr>{''.join(f'<td>{v}</td>' for v in r.values())}</tr>"
            for r in records
        )
        headers_html = ""
        if records:
            headers_html = "".join(f"<th>{k}</th>" for k in records[0].keys())

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>{title}</title>
          <style>
            body {{ font-family: Arial, sans-serif; font-size: 11px; margin: 20px; }}
            h1 {{ font-size: 16px; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; word-break: break-all; }}
            th {{ background: #f0f0f0; font-weight: bold; }}
            tr:nth-child(even) {{ background: #f9f9f9; }}
            .meta {{ color: #666; font-size: 10px; margin-bottom: 12px; }}
          </style>
        </head>
        <body>
          <h1>{title}</h1>
          <p class="meta">Generated: {datetime.now(timezone.utc).isoformat()} | Records: {len(records)}</p>
          <table>
            <thead><tr>{headers_html}</tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </body>
        </html>
        """
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="WeasyPrint not installed; PDF export unavailable",
        ) from exc


# ── Routes ────────────────────────────────────────────────────────────────────

MIME_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

FILE_EXTENSIONS = {"json": "json", "csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}


@router.post("/")
async def export_data(
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """
    Export intelligence data in the requested format.

    Supported resource_types: ``entities``, ``case``, ``relationships``.
    Supported formats: ``json``, ``csv``, ``xlsx``, ``pdf``.
    """
    fmt = body.format.lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=422, detail=f"format must be one of {EXPORT_FORMATS}"
        )

    records: List[Dict[str, Any]] = []
    filename_prefix = "osint_export"

    if body.resource_type == "entities":
        filename_prefix = "entities"
        if body.resource_ids:
            entities = [
                e for e in [await get_by_id(session, Entity, eid) for eid in body.resource_ids]
                if e is not None
            ]
        else:
            entities = await get_all(session, Entity, limit=10000, filters=body.filters or None)
        records = [_entity_to_dict(e) for e in entities]

        if body.include_relationships:
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            entity_ids = [e.id for e in entities]
            rel_result = await session.execute(
                select(Relationship).where(
                    Relationship.source_entity_id.in_(entity_ids)
                    | Relationship.target_entity_id.in_(entity_ids)
                )
            )
            rel_records = [_relationship_to_dict(r) for r in rel_result.scalars().all()]
            records = {"entities": records, "relationships": rel_records}  # type: ignore[assignment]

    elif body.resource_type == "case":
        filename_prefix = "case"
        if not body.resource_ids:
            raise HTTPException(status_code=400, detail="resource_ids required for case export")
        for cid in body.resource_ids:
            case = await get_by_id(session, Case, cid)
            if case is None:
                continue
            case_dict = _case_to_dict(case)
            # Include associated entities
            ce_list = await get_all(session, CaseEntity, filters={"case_id": cid})
            case_entities = []
            for ce in ce_list:
                entity = await get_by_id(session, Entity, ce.entity_id)
                if entity:
                    case_entities.append(_entity_to_dict(entity))
            case_dict["entities"] = case_entities
            records.append(case_dict)

    elif body.resource_type == "relationships":
        filename_prefix = "relationships"
        if body.resource_ids:
            rels = [
                r
                for r in [await get_by_id(session, Relationship, rid) for rid in body.resource_ids]
                if r is not None
            ]
        else:
            rels = await get_all(session, Relationship, limit=10000)
        records = [_relationship_to_dict(r) for r in rels]
    else:
        raise HTTPException(
            status_code=422,
            detail="resource_type must be one of: entities, case, relationships",
        )

    # When records is a dict (nested export), JSON-only
    if isinstance(records, dict):
        content = _to_json(records)  # type: ignore[arg-type]
        fmt = "json"
    elif fmt == "json":
        content = _to_json(records)
    elif fmt == "csv":
        content = _to_csv(records)
    elif fmt == "xlsx":
        content = _to_xlsx(records, sheet_name=filename_prefix[:31])
    elif fmt == "pdf":
        content = _to_pdf(records, title=f"OSINT {filename_prefix.capitalize()} Report")
    else:
        content = _to_json(records)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.{FILE_EXTENSIONS.get(fmt, fmt)}"

    return Response(
        content=content,
        media_type=MIME_TYPES.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/entities/{entity_id}")
async def export_single_entity(
    entity_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|csv|xlsx|pdf)$"),
    include_relationships: bool = False,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Export a single entity and optionally its relationships."""
    entity = await get_by_id(session, Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    records: Any = [_entity_to_dict(entity)]

    if include_relationships:
        from storage.database.postgres.queries import get_entity_relationships
        rels = await get_entity_relationships(session, entity_id)
        rel_records = [_relationship_to_dict(r) for r in rels]
        records = {"entity": _entity_to_dict(entity), "relationships": rel_records}

    fmt = format.lower()
    if isinstance(records, dict):
        content = _to_json(records)
        fmt = "json"
    elif fmt == "json":
        content = _to_json(records)
    elif fmt == "csv":
        content = _to_csv(records)
    elif fmt == "xlsx":
        content = _to_xlsx(records, sheet_name="Entity")
    elif fmt == "pdf":
        content = _to_pdf(records, title=f"Entity: {entity.name}")
    else:
        content = _to_json(records)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"entity_{entity_id}_{timestamp}.{FILE_EXTENSIONS.get(fmt, fmt)}"
    return Response(
        content=content,
        media_type=MIME_TYPES.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cases/{case_id}")
async def export_case_report(
    case_id: uuid.UUID,
    format: str = Query(default="pdf", pattern="^(json|csv|xlsx|pdf)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Export a complete case report including all associated entities."""
    case = await get_by_id(session, Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    ce_list = await get_all(session, CaseEntity, filters={"case_id": case_id})
    entities = [
        e
        for e in [await get_by_id(session, Entity, ce.entity_id) for ce in ce_list]
        if e is not None
    ]

    case_dict = _case_to_dict(case)
    entity_records = [_entity_to_dict(e) for e in entities]
    fmt = format.lower()

    if fmt == "json":
        payload = {**case_dict, "entities": entity_records}
        content = _to_json(payload)
    elif fmt == "csv":
        content = _to_csv(entity_records)
    elif fmt == "xlsx":
        content = _to_xlsx(entity_records, sheet_name=case.name[:31])
    elif fmt == "pdf":
        all_records = [case_dict] + entity_records
        content = _to_pdf(all_records, title=f"Case Report: {case.name}")
    else:
        content = _to_json(case_dict)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"case_{case_id}_{timestamp}.{FILE_EXTENSIONS.get(fmt, fmt)}"
    return Response(
        content=content,
        media_type=MIME_TYPES.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
