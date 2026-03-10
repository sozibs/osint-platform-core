"""
Async file manager.

Abstracts over two storage back-ends:
  1. S3-compatible object storage (MinIO, AWS S3, GCS via compatibility layer)
  2. Local filesystem fallback when S3 is not configured

All public methods are async and safe to call from FastAPI route handlers or
Celery tasks.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiofiles
import aiofiles.os

from config import settings

logger = logging.getLogger(__name__)

# Allowed MIME types (add more as needed)
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # Data formats
        "text/csv",
        "application/json",
        "application/xml",
        "text/xml",
        "text/plain",
        # Images
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/tiff",
        "image/bmp",
        # Archives
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-bzip2",
        "application/x-7z-compressed",
        # Miscellaneous OSINT-relevant
        "application/octet-stream",
    }
)

# Local fallback directory (relative to project root)
LOCAL_STORAGE_ROOT = Path(os.getenv("LOCAL_STORAGE_PATH", "/tmp/osint-files"))


class FileManager:
    """
    High-level file management service.

    Automatically routes to S3 when ``settings.S3_ENDPOINT`` is configured,
    falling back to the local filesystem otherwise.
    """

    def __init__(self) -> None:
        self._s3: Optional[Any] = None
        self._use_s3 = bool(settings.S3_ENDPOINT and settings.S3_ACCESS_KEY)

        if self._use_s3:
            from storage.files.s3_adapter import S3Adapter

            self._s3 = S3Adapter(
                endpoint=settings.S3_ENDPOINT,
                bucket=settings.S3_BUCKET,
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
            )
            logger.info("FileManager using S3 backend at %s", settings.S3_ENDPOINT)
        else:
            LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
            logger.info("FileManager using local filesystem at %s", LOCAL_STORAGE_ROOT)

    # ── Validation helpers ────────────────────────────────────────────────────

    def _validate_file(self, data: bytes, content_type: str) -> None:
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(
                f"File size {len(data)} bytes exceeds the maximum allowed "
                f"{settings.MAX_FILE_SIZE_MB} MB."
            )
        # Normalise and check MIME type
        mime = content_type.split(";")[0].strip().lower()
        if mime not in ALLOWED_MIME_TYPES:
            raise ValueError(
                f"File type '{mime}' is not allowed. "
                f"Permitted types: {sorted(ALLOWED_MIME_TYPES)}"
            )

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _build_key(filename: str, user_id: UUID) -> str:
        """Construct a namespaced storage key / path."""
        ext = Path(filename).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        return f"{user_id}/{date_prefix}/{unique_name}"

    # ── Public API ────────────────────────────────────────────────────────────

    async def save_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        user_id: UUID,
    ) -> str:
        """
        Persist *file_data* and return the storage key / path.

        Raises ``ValueError`` if the file fails validation.
        """
        self._validate_file(file_data, content_type)
        sha256 = self._sha256(file_data)
        key = self._build_key(filename, user_id)
        metadata = {
            "original_filename": filename,
            "sha256": sha256,
            "user_id": str(user_id),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        if self._use_s3 and self._s3 is not None:
            await self._s3.upload_file(
                key=key,
                data=file_data,
                content_type=content_type,
                metadata=metadata,
            )
        else:
            await self._save_local(key, file_data)

        logger.info("Saved file key=%s sha256=%s size=%d", key, sha256, len(file_data))
        return key

    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content by its storage key / path."""
        if self._use_s3 and self._s3 is not None:
            return await self._s3.download_file(file_path)
        return await self._load_local(file_path)

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file by its storage key / path. Returns True on success."""
        if self._use_s3 and self._s3 is not None:
            return await self._s3.delete_file(file_path)
        return await self._delete_local(file_path)

    async def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Return metadata for all files under *prefix*."""
        if self._use_s3 and self._s3 is not None:
            return await self._s3.list_files(prefix)
        return await self._list_local(prefix)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Return basic metadata for a file (size, content_type, sha256, etc.)."""
        if self._use_s3 and self._s3 is not None:
            files = await self._s3.list_files(file_path)
            if files:
                return files[0]
            return {}
        return await self._local_metadata(file_path)

    async def get_presigned_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a pre-signed URL for direct browser download.

        Returns None when using the local filesystem backend.
        """
        if self._use_s3 and self._s3 is not None:
            return await self._s3.get_presigned_url(file_path, expires_in)
        return None

    # ── Local filesystem helpers ──────────────────────────────────────────────

    async def _save_local(self, key: str, data: bytes) -> None:
        target = LOCAL_STORAGE_ROOT / key
        await aiofiles.os.makedirs(str(target.parent), exist_ok=True)
        async with aiofiles.open(target, "wb") as fh:
            await fh.write(data)

    async def _load_local(self, key: str) -> bytes:
        target = LOCAL_STORAGE_ROOT / key
        if not await aiofiles.os.path.exists(str(target)):
            raise FileNotFoundError(f"File not found: {key}")
        async with aiofiles.open(target, "rb") as fh:
            return await fh.read()

    async def _delete_local(self, key: str) -> bool:
        target = LOCAL_STORAGE_ROOT / key
        try:
            await aiofiles.os.remove(str(target))
            return True
        except FileNotFoundError:
            return False
        except Exception as exc:
            logger.error("Local delete failed for %s: %s", key, exc)
            return False

    async def _list_local(self, prefix: str) -> List[Dict[str, Any]]:
        root = LOCAL_STORAGE_ROOT / prefix if prefix else LOCAL_STORAGE_ROOT
        results: List[Dict[str, Any]] = []
        if not root.exists():
            return results
        for path in root.rglob("*"):
            if path.is_file():
                stat = path.stat()
                mime, _ = mimetypes.guess_type(path.name)
                results.append(
                    {
                        "key": str(path.relative_to(LOCAL_STORAGE_ROOT)),
                        "size": stat.st_size,
                        "content_type": mime or "application/octet-stream",
                        "last_modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
        return results

    async def _local_metadata(self, key: str) -> Dict[str, Any]:
        target = LOCAL_STORAGE_ROOT / key
        if not await aiofiles.os.path.exists(str(target)):
            return {}
        stat = target.stat()
        mime, _ = mimetypes.guess_type(target.name)
        return {
            "key": key,
            "size": stat.st_size,
            "content_type": mime or "application/octet-stream",
            "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
