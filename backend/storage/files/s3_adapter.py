"""
boto3 / aioboto3 S3-compatible object storage adapter.

Supports MinIO and any S3-compatible endpoint.  Uses ``aioboto3`` when
available for fully async I/O, falling back to running synchronous boto3
calls inside a thread-pool executor.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Prefer aioboto3 (truly async); fall back to sync boto3 + executor
try:
    import aioboto3 as _aioboto3

    _AIOBOTO3_AVAILABLE = True
except ImportError:
    _AIOBOTO3_AVAILABLE = False
    logger.info("aioboto3 not installed; S3 adapter will use boto3 via executor")

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed; S3 features will be unavailable")


class S3Adapter:
    """
    Async S3 adapter that works with any S3-compatible endpoint.

    Parameters
    ----------
    endpoint:
        URL of the S3 endpoint, e.g. ``http://localhost:9000`` for MinIO.
    bucket:
        Bucket name where all files are stored.
    access_key / secret_key:
        Credentials for the S3 service.
    """

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> None:
        self._endpoint = endpoint
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._session: Optional[Any] = None  # aioboto3 session
        self._sync_client: Optional[Any] = None  # boto3 client (fallback)

        if not _BOTO3_AVAILABLE and not _AIOBOTO3_AVAILABLE:
            raise RuntimeError("Neither boto3 nor aioboto3 is installed.")

        if not _AIOBOTO3_AVAILABLE and _BOTO3_AVAILABLE:
            self._sync_client = self._make_sync_client()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _make_sync_client(self) -> Any:
        return boto3.client(  # type: ignore[union-attr]
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
        )

    def _s3_kwargs(self) -> Dict[str, Any]:
        return {
            "endpoint_url": self._endpoint,
            "aws_access_key_id": self._access_key,
            "aws_secret_access_key": self._secret_key,
            "region_name": self._region,
        }

    async def _ensure_bucket(self, client: Any) -> None:
        """Create the bucket if it does not already exist."""
        try:
            await client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                await client.create_bucket(Bucket=self._bucket)
                logger.info("Created S3 bucket %s", self._bucket)
            except Exception as exc:
                logger.warning("Could not create bucket %s: %s", self._bucket, exc)

    # ── Public async API ──────────────────────────────────────────────────────

    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload *data* under *key* in the configured bucket. Returns the key."""
        put_kwargs: Dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if metadata:
            put_kwargs["Metadata"] = {k: str(v) for k, v in metadata.items()}

        if _AIOBOTO3_AVAILABLE:
            session = _aioboto3.Session()  # type: ignore[union-attr]
            async with session.client("s3", **self._s3_kwargs()) as client:
                await self._ensure_bucket(client)
                await client.put_object(**put_kwargs)
        else:
            loop = asyncio.get_event_loop()
            client = self._sync_client or self._make_sync_client()
            await loop.run_in_executor(None, partial(client.put_object, **put_kwargs))

        logger.debug("Uploaded S3 key=%s size=%d", key, len(data))
        return key

    async def download_file(self, key: str) -> bytes:
        """Download and return the raw bytes stored under *key*."""
        if _AIOBOTO3_AVAILABLE:
            session = _aioboto3.Session()  # type: ignore[union-attr]
            async with session.client("s3", **self._s3_kwargs()) as client:
                response = await client.get_object(Bucket=self._bucket, Key=key)
                body = response["Body"]
                return await body.read()
        else:
            loop = asyncio.get_event_loop()
            client = self._sync_client or self._make_sync_client()

            def _download() -> bytes:
                resp = client.get_object(Bucket=self._bucket, Key=key)
                return resp["Body"].read()

            return await loop.run_in_executor(None, _download)

    async def delete_file(self, key: str) -> bool:
        """Delete the object stored under *key*. Returns True on success."""
        try:
            if _AIOBOTO3_AVAILABLE:
                session = _aioboto3.Session()  # type: ignore[union-attr]
                async with session.client("s3", **self._s3_kwargs()) as client:
                    await client.delete_object(Bucket=self._bucket, Key=key)
            else:
                loop = asyncio.get_event_loop()
                client = self._sync_client or self._make_sync_client()
                await loop.run_in_executor(
                    None, partial(client.delete_object, Bucket=self._bucket, Key=key)
                )
            return True
        except Exception as exc:
            logger.error("S3 delete_file failed for key=%s: %s", key, exc)
            return False

    async def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Return metadata dicts for all objects under *prefix*."""
        results: List[Dict[str, Any]] = []
        list_kwargs: Dict[str, Any] = {"Bucket": self._bucket}
        if prefix:
            list_kwargs["Prefix"] = prefix

        try:
            if _AIOBOTO3_AVAILABLE:
                session = _aioboto3.Session()  # type: ignore[union-attr]
                async with session.client("s3", **self._s3_kwargs()) as client:
                    paginator = client.get_paginator("list_objects_v2")
                    async for page in paginator.paginate(**list_kwargs):
                        for obj in page.get("Contents", []):
                            results.append(
                                {
                                    "key": obj["Key"],
                                    "size": obj["Size"],
                                    "last_modified": obj["LastModified"].isoformat(),
                                    "etag": obj.get("ETag", "").strip('"'),
                                }
                            )
            else:
                loop = asyncio.get_event_loop()
                client = self._sync_client or self._make_sync_client()

                def _list() -> List[Dict[str, Any]]:
                    out: List[Dict[str, Any]] = []
                    paginator = client.get_paginator("list_objects_v2")
                    for page in paginator.paginate(**list_kwargs):
                        for obj in page.get("Contents", []):
                            out.append(
                                {
                                    "key": obj["Key"],
                                    "size": obj["Size"],
                                    "last_modified": obj["LastModified"].isoformat(),
                                    "etag": obj.get("ETag", "").strip('"'),
                                }
                            )
                    return out

                results = await loop.run_in_executor(None, _list)
        except Exception as exc:
            logger.error("S3 list_files failed: %s", exc)

        return results

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL valid for *expires_in* seconds."""
        params = {"Bucket": self._bucket, "Key": key}
        if _AIOBOTO3_AVAILABLE:
            session = _aioboto3.Session()  # type: ignore[union-attr]
            async with session.client("s3", **self._s3_kwargs()) as client:
                return await client.generate_presigned_url(
                    "get_object", Params=params, ExpiresIn=expires_in
                )
        else:
            loop = asyncio.get_event_loop()
            client = self._sync_client or self._make_sync_client()
            return await loop.run_in_executor(
                None,
                partial(
                    client.generate_presigned_url,
                    "get_object",
                    Params=params,
                    ExpiresIn=expires_in,
                ),
            )

    async def file_exists(self, key: str) -> bool:
        """Return True if an object with *key* exists in the bucket."""
        try:
            if _AIOBOTO3_AVAILABLE:
                session = _aioboto3.Session()  # type: ignore[union-attr]
                async with session.client("s3", **self._s3_kwargs()) as client:
                    await client.head_object(Bucket=self._bucket, Key=key)
            else:
                loop = asyncio.get_event_loop()
                client = self._sync_client or self._make_sync_client()
                await loop.run_in_executor(
                    None, partial(client.head_object, Bucket=self._bucket, Key=key)
                )
            return True
        except Exception:
            return False
