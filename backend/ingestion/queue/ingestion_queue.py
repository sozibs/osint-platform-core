"""Celery tasks for async data ingestion."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from celery import Celery
from celery.utils.log import get_task_logger

# Import settings lazily to allow workers to set env before import
from config import settings

logger = get_task_logger(__name__)

celery_app = Celery(
    "osint_ingestion",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=300,
    task_time_limit=600,
    result_expires=86400,  # 1 day
)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a synchronous Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── File ingestion ─────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="ingestion.ingest_file",
)
def ingest_file_task(
    self,
    file_path: str,
    source_id: str,
    user_id: str,
    mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ingest a file from local storage or object storage path.

    The file is read from *file_path*, auto-detected for format, parsed,
    then handed off to ``normalize_and_store_task``.
    """
    logger.info("ingest_file_task: file=%s source=%s user=%s", file_path, source_id, user_id)
    try:
        from ingestion.connectors.file_connector import FileConnector

        filename = os.path.basename(file_path)

        with open(file_path, "rb") as fh:
            file_data = fh.read()

        connector = FileConnector()
        records = _run_async(connector.ingest(file_data, filename, mapping=mapping))

        logger.info("Parsed %d records from file %s.", len(records), file_path)

        result = normalize_and_store_task.delay(records, source_id, user_id)
        return {
            "status": "queued",
            "file_path": file_path,
            "source_id": source_id,
            "user_id": user_id,
            "records_parsed": len(records),
            "normalize_task_id": result.id,
        }

    except FileNotFoundError as exc:
        logger.error("File not found: %s", file_path)
        raise self.retry(exc=exc, countdown=60)

    except Exception as exc:
        logger.exception("ingest_file_task failed for %s: %s", file_path, exc)
        raise self.retry(exc=exc, countdown=int(60 * (2 ** self.request.retries)))


# ── URL ingestion ──────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="ingestion.ingest_url",
)
def ingest_url_task(
    self,
    url: str,
    source_type: str,
    config: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """Ingest data from a URL based on source_type (api | rss | web).

    *config* may contain connector-specific settings such as ``api_key``,
    ``rate_limit_per_second``, ``page_size``, etc.
    """
    logger.info("ingest_url_task: url=%s type=%s user=%s", url, source_type, user_id)
    source_id = config.get("source_id", "")

    try:
        records: List[Dict[str, Any]] = []

        if source_type == "rss":
            from ingestion.connectors.rss_connector import RSSConnector
            connector = RSSConnector(
                rate_limit_per_second=config.get("rate_limit_per_second", 1.0)
            )

            async def fetch_rss() -> List[Dict[str, Any]]:
                async with connector:
                    result = await connector.fetch_feed(url)
                    return result.get("entries", [])

            records = _run_async(fetch_rss())

        elif source_type == "web":
            from ingestion.connectors.web_scraper import EthicalWebScraper
            scraper = EthicalWebScraper(
                rate_limit_per_second=config.get("rate_limit_per_second", 0.5),
                max_depth=config.get("max_depth", 2),
            )

            async def fetch_web() -> List[Dict[str, Any]]:
                async with scraper:
                    pages = await scraper.scrape_with_depth(
                        url, max_pages=config.get("max_pages", 10)
                    )
                    entities: List[Dict[str, Any]] = []
                    for page in pages:
                        extracted = await scraper.extract_entities(page.get("text", ""), page["url"])
                        entities.extend(extracted)
                    return entities

            records = _run_async(fetch_web())

        elif source_type == "api":
            from ingestion.connectors.api_connector import APIConnector
            connector_api = APIConnector(
                base_url=url,
                api_key=config.get("api_key"),
                headers=config.get("headers"),
                timeout=config.get("timeout", 30),
                rate_limit_per_second=config.get("rate_limit_per_second", 1.0),
            )

            async def fetch_api() -> List[Dict[str, Any]]:
                async with connector_api:
                    return await connector_api.fetch_paginated(
                        config.get("endpoint", "/"),
                        page_size=config.get("page_size", 100),
                    )

            records = _run_async(fetch_api())

        else:
            raise ValueError(f"Unsupported source_type: {source_type}")

        logger.info("Fetched %d records from %s (%s).", len(records), url, source_type)

        if records:
            result = normalize_and_store_task.delay(records, source_id, user_id)
            normalize_task_id = result.id
        else:
            normalize_task_id = None

        return {
            "status": "queued" if records else "no_data",
            "url": url,
            "source_type": source_type,
            "source_id": source_id,
            "user_id": user_id,
            "records_fetched": len(records),
            "normalize_task_id": normalize_task_id,
        }

    except Exception as exc:
        logger.exception("ingest_url_task failed for %s: %s", url, exc)
        raise self.retry(exc=exc, countdown=int(300 * (2 ** self.request.retries)))


# ── RSS polling ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=3600,
    name="ingestion.poll_rss_feed",
)
def poll_rss_feed_task(self, source_id: str) -> Dict[str, Any]:
    """Periodic task to poll a stored RSS feed source for new entries.

    Fetches the Source record from the database, retrieves the feed URL
    and last-fetched metadata, then enqueues new entries for processing.
    """
    logger.info("poll_rss_feed_task: source_id=%s", source_id)

    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from storage.database.postgres.models import Source
        from ingestion.connectors.rss_connector import RSSConnector
        from datetime import datetime, timezone

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url, future=True)

        with Session(engine) as session:
            source = session.get(Source, source_id)
            if not source:
                logger.error("Source %s not found.", source_id)
                return {"status": "error", "error": "source_not_found"}

            if not source.is_active:
                return {"status": "skipped", "reason": "source_inactive"}

            feed_url = source.url
            config: Dict[str, Any] = source.config or {}
            last_modified_str = config.get("last_modified")
            etag = config.get("etag")

            last_modified = None
            if last_modified_str:
                try:
                    last_modified = datetime.fromisoformat(last_modified_str)
                except ValueError:
                    pass

        connector = RSSConnector(rate_limit_per_second=1.0)

        async def fetch() -> Dict[str, Any]:
            async with connector:
                return await connector.fetch_feed(
                    feed_url, last_modified=last_modified, etag=etag
                )

        result = _run_async(fetch())

        if result.get("not_modified"):
            logger.info("Feed %s not modified since last poll.", feed_url)
            return {"status": "not_modified", "source_id": source_id}

        entries = result.get("entries", [])
        new_etag = result.get("etag")
        new_modified = result.get("modified")

        # Persist updated etag/modified back to source config
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if source:
                cfg = dict(source.config or {})
                if new_etag:
                    cfg["etag"] = new_etag
                if new_modified:
                    cfg["last_modified"] = (
                        new_modified.isoformat()
                        if hasattr(new_modified, "isoformat")
                        else str(new_modified)
                    )
                source.config = cfg
                session.commit()

        engine.dispose()

        if entries:
            user_id = config.get("created_by", "system")
            norm_result = normalize_and_store_task.delay(entries, source_id, user_id)
            return {
                "status": "processed",
                "source_id": source_id,
                "entries_found": len(entries),
                "normalize_task_id": norm_result.id,
            }

        return {"status": "no_new_entries", "source_id": source_id}

    except Exception as exc:
        logger.exception("poll_rss_feed_task failed for source %s: %s", source_id, exc)
        raise self.retry(exc=exc, countdown=int(3600 * (2 ** self.request.retries)))


# ── API source polling ─────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="ingestion.ingest_api_source",
)
def ingest_api_source_task(
    self, source_id: str, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Fetch data from a configured API source and queue for normalization."""
    logger.info("ingest_api_source_task: source_id=%s", source_id)

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from storage.database.postgres.models import Source
        from ingestion.connectors.api_connector import APIConnector

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url, future=True)

        with Session(engine) as session:
            source = session.get(Source, source_id)
            if not source:
                logger.error("API source %s not found.", source_id)
                return {"status": "error", "error": "source_not_found"}
            if not source.is_active:
                return {"status": "skipped", "reason": "source_inactive"}
            base_url = source.url or config.get("base_url", "")
            merged_config: Dict[str, Any] = dict(source.config or {})
            merged_config.update(config)

        engine.dispose()

        api_connector = APIConnector(
            base_url=base_url,
            api_key=merged_config.get("api_key"),
            headers=merged_config.get("headers"),
            timeout=merged_config.get("timeout", 30),
            rate_limit_per_second=merged_config.get("rate_limit_per_second", 1.0),
        )

        async def fetch() -> List[Dict[str, Any]]:
            async with api_connector:
                endpoint = merged_config.get("endpoint", "/")
                if merged_config.get("paginated", True):
                    return await api_connector.fetch_paginated(
                        endpoint,
                        page_param=merged_config.get("page_param", "page"),
                        page_size_param=merged_config.get("page_size_param", "per_page"),
                        page_size=merged_config.get("page_size", 100),
                    )
                else:
                    result = await api_connector.fetch(endpoint)
                    data = result["data"]
                    return data if isinstance(data, list) else [data]

        records = _run_async(fetch())
        logger.info("Fetched %d records from API source %s.", len(records), source_id)

        if not records:
            return {"status": "no_data", "source_id": source_id}

        user_id = merged_config.get("created_by", "system")
        norm_result = normalize_and_store_task.delay(records, source_id, user_id)

        return {
            "status": "queued",
            "source_id": source_id,
            "records_fetched": len(records),
            "normalize_task_id": norm_result.id,
        }

    except Exception as exc:
        logger.exception("ingest_api_source_task failed for %s: %s", source_id, exc)
        raise self.retry(exc=exc, countdown=int(300 * (2 ** self.request.retries)))


# ── Normalize and store ────────────────────────────────────────────────────────

@celery_app.task(
    name="ingestion.normalize_and_store",
    max_retries=3,
    default_retry_delay=120,
)
def normalize_and_store_task(
    records: List[Dict[str, Any]],
    source_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Normalize raw records and persist entities to the database.

    This task is intentionally kept simple: it delegates to IngestionProcessor
    which handles entity extraction, dedup-candidate detection, and storage.
    """
    logger.info(
        "normalize_and_store_task: %d records, source=%s, user=%s",
        len(records),
        source_id,
        user_id,
    )

    try:
        from ingestion.queue.processor import IngestionProcessor
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from storage.database.postgres.models import Source

        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        engine = create_engine(sync_url, future=True)

        with Session(engine) as session:
            source = session.get(Source, source_id)
            if not source:
                logger.warning("Source %s not found; storing without source ref.", source_id)
                source = None

        processor = IngestionProcessor()

        async def run_processing() -> Dict[str, Any]:
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            async_engine = create_async_engine(settings.DATABASE_URL, future=True)
            async with AsyncSession(async_engine) as async_session:
                result = await processor.process_records(records, source, user_id, async_session)
            await async_engine.dispose()
            return result

        result_dict = _run_async(run_processing())
        engine.dispose()

        logger.info(
            "normalize_and_store_task complete: %s entities created.",
            result_dict.get("entities_created", 0),
        )
        return result_dict

    except Exception as exc:
        logger.exception("normalize_and_store_task failed: %s", exc)
        raise
