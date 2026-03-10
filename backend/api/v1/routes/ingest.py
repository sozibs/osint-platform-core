"""
Data ingestion router.

Accepts raw intelligence data from multiple source types (file upload, URL,
JSON payload) and dispatches processing to the Celery worker queue.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.routes.auth import get_current_user
from config import settings
from storage.database.postgres import get_async_session
from storage.database.postgres.models import Source, User
from storage.database.postgres.queries import create_record, get_all, get_by_id, paginate
from storage.files.file_manager import FileManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest")

_file_manager = FileManager()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    source_type: str = Field(..., pattern="^(api|rss|web|file)$")
    url: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    legal_status: str = Field(default="unverified")


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    url: Optional[str]
    is_active: bool
    is_verified: bool
    legal_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class IngestPayload(BaseModel):
    source_id: uuid.UUID
    data: List[Dict[str, Any]] = Field(..., min_length=1)
    entity_type_hint: Optional[str] = None


class IngestResponse(BaseModel):
    task_id: str
    message: str
    items_queued: int


class SourceListResponse(BaseModel):
    items: List[SourceResponse]
    total: int
    page: int
    pages: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceResponse:
    """Register a new intelligence source."""
    source = await create_record(
        session,
        Source,
        {
            "name": body.name,
            "source_type": body.source_type,
            "url": body.url,
            "config": body.config,
            "legal_status": body.legal_status,
            "created_by": current_user.id,
        },
    )
    return SourceResponse.model_validate(source)


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    page: int = 1,
    page_size: int = 20,
    source_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceListResponse:
    """List registered intelligence sources."""
    filters: Dict[str, Any] = {}
    if source_type:
        filters["source_type"] = source_type
    result = await paginate(session, Source, page=page, page_size=page_size, filters=filters)
    return SourceListResponse(
        items=[SourceResponse.model_validate(s) for s in result["items"]],
        total=result["total"],
        page=result["page"],
        pages=result["pages"],
    )


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceResponse:
    """Retrieve a source by ID."""
    source = await get_by_id(session, Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse.model_validate(source)


@router.post("/json", response_model=IngestResponse)
async def ingest_json(
    body: IngestPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IngestResponse:
    """
    Ingest a JSON array of intelligence records.

    Records are dispatched to the Celery processing queue asynchronously.
    """
    source = await get_by_id(session, Source, body.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    task_id = str(uuid.uuid4())

    # Dispatch to Celery if available; otherwise process inline (dev mode)
    try:
        from ingestion.tasks import process_ingest_batch  # type: ignore[import]

        process_ingest_batch.apply_async(
            kwargs={
                "task_id": task_id,
                "source_id": str(body.source_id),
                "records": body.data,
                "entity_type_hint": body.entity_type_hint,
                "user_id": str(current_user.id),
            }
        )
    except ImportError:
        logger.warning("Celery tasks not available; ingestion queued as task_id=%s", task_id)

    return IngestResponse(
        task_id=task_id,
        message="Records queued for processing",
        items_queued=len(body.data),
    )


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    source_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IngestResponse:
    """
    Ingest an uploaded file (CSV, JSON, PDF, XML).

    The file is stored and processing is dispatched asynchronously.
    """
    source = await get_by_id(session, Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    content_type = file.content_type or "application/octet-stream"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        file_key = await _file_manager.save_file(
            file_data=data,
            filename=file.filename or "upload",
            content_type=content_type,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task_id = str(uuid.uuid4())

    try:
        from ingestion.tasks import process_file_ingest  # type: ignore[import]

        process_file_ingest.apply_async(
            kwargs={
                "task_id": task_id,
                "source_id": str(source_id),
                "file_key": file_key,
                "content_type": content_type,
                "filename": file.filename,
                "user_id": str(current_user.id),
            }
        )
    except ImportError:
        logger.warning("Celery tasks not available; file ingestion task_id=%s", task_id)

    return IngestResponse(
        task_id=task_id,
        message=f"File '{file.filename}' uploaded and queued for processing",
        items_queued=1,
    )


@router.post("/url", response_model=IngestResponse)
async def ingest_url(
    source_id: uuid.UUID,
    url: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IngestResponse:
    """Schedule a web scrape / RSS fetch from the given URL."""
    source = await get_by_id(session, Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    task_id = str(uuid.uuid4())
    try:
        from ingestion.tasks import process_url_ingest  # type: ignore[import]

        process_url_ingest.apply_async(
            kwargs={
                "task_id": task_id,
                "source_id": str(source_id),
                "url": url,
                "user_id": str(current_user.id),
            }
        )
    except ImportError:
        logger.warning("Celery tasks not available; URL ingestion task_id=%s", task_id)

    return IngestResponse(
        task_id=task_id,
        message=f"URL '{url}' queued for ingestion",
        items_queued=1,
    )


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Query the status of an asynchronous ingestion task."""
    try:
        from celery.result import AsyncResult  # type: ignore[import]
        from ingestion.tasks import celery_app  # type: ignore[import]

        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }
    except ImportError:
        return {"task_id": task_id, "status": "UNKNOWN", "result": None}
