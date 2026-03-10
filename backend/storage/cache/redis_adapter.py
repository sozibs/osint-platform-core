"""
Async Redis adapter backed by ``redis.asyncio``.

Used for:
- Response caching
- Session / token storage
- Rate-limit counters
- Pub/Sub messaging between workers
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub
from redis.asyncio.connection import ConnectionPool

logger = logging.getLogger(__name__)

# Sentinel value used to distinguish a missing key from a stored ``None``.
_MISSING = object()


class RedisAdapter:
    """
    Production-ready async Redis wrapper.

    All values are JSON-serialised so that any JSON-serialisable Python object
    can be stored and retrieved without the caller caring about encoding.

    Usage::

        redis = RedisAdapter(url="redis://localhost:6379/0")
        await redis.connect()
        await redis.set("key", {"data": 42}, ttl=300)
        value = await redis.get("key")   # {"data": 42}
        await redis.close()
    """

    def __init__(self, url: str, max_connections: int = 20) -> None:
        self._url = url
        self._max_connections = max_connections
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[aioredis.Redis] = None  # type: ignore[type-arg]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Create the connection pool and verify reachability."""
        self._pool = aioredis.ConnectionPool.from_url(
            self._url,
            max_connections=self._max_connections,
            decode_responses=False,  # We handle encoding ourselves
        )
        self._client = aioredis.Redis(connection_pool=self._pool)
        try:
            await self._client.ping()
            logger.info("Redis connection established at %s", self._url)
        except Exception as exc:
            logger.error("Redis connection failed: %s", exc)
            raise

    async def close(self) -> None:
        """Gracefully close the connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
        logger.info("Redis connection closed")

    def _ensure_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        if self._client is None:
            raise RuntimeError("RedisAdapter.connect() must be called before using the client.")
        return self._client

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _serialise(value: Any) -> bytes:
        return json.dumps(value, default=str).encode("utf-8")

    @staticmethod
    def _deserialise(raw: Optional[bytes]) -> Any:
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Return raw bytes as a last resort (e.g. binary blobs)
            return raw

    # ── Core operations ───────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        """Return the value stored at *key*, or None if the key does not exist."""
        client = self._ensure_client()
        raw = await client.get(key)
        return self._deserialise(raw)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store *value* at *key*.

        Parameters
        ----------
        ttl:
            Expiry in seconds.  If omitted the key persists indefinitely.
        """
        client = self._ensure_client()
        data = self._serialise(value)
        if ttl is not None:
            return bool(await client.setex(key, ttl, data))
        return bool(await client.set(key, data))

    async def delete(self, key: str) -> bool:
        """Delete *key*. Returns True if the key existed."""
        client = self._ensure_client()
        result = await client.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Return True if *key* exists in Redis."""
        client = self._ensure_client()
        return bool(await client.exists(key))

    async def expire(self, key: str, ttl: int) -> bool:
        """Set (or update) the TTL on an existing key. Returns True on success."""
        client = self._ensure_client()
        return bool(await client.expire(key, ttl))

    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomically increment an integer counter and return the new value."""
        client = self._ensure_client()
        return int(await client.incrby(key, amount))

    # ── Batch operations ──────────────────────────────────────────────────────

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Retrieve multiple keys in a single round-trip (MGET).

        Returns a dict mapping each key to its deserialised value (or None).
        """
        if not keys:
            return {}
        client = self._ensure_client()
        raw_values = await client.mget(*keys)
        return {
            key: self._deserialise(raw)
            for key, raw in zip(keys, raw_values)
        }

    async def set_many(
        self, mapping: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Store multiple key-value pairs.  Uses a pipeline for efficiency.

        When *ttl* is provided each key is given the same expiry.
        """
        if not mapping:
            return
        client = self._ensure_client()
        async with client.pipeline(transaction=False) as pipe:
            for key, value in mapping.items():
                data = self._serialise(value)
                if ttl is not None:
                    pipe.setex(key, ttl, data)
                else:
                    pipe.set(key, data)
            await pipe.execute()

    # ── Pattern operations ────────────────────────────────────────────────────

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching *pattern* (uses SCAN to avoid blocking).

        Returns the number of keys deleted.
        """
        client = self._ensure_client()
        deleted = 0
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1
        return deleted

    # ── Pub / Sub ─────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> int:
        """Publish *message* to *channel*. Returns the number of subscribers."""
        client = self._ensure_client()
        payload = self._serialise(message)
        return int(await client.publish(channel, payload))

    async def subscribe(
        self, channel: str, callback: Callable[[Any], Any]
    ) -> None:
        """
        Subscribe to *channel* and invoke *callback(message)* for each message.

        This coroutine runs until cancelled.  Run it as a background task::

            asyncio.create_task(redis.subscribe("events", handler))
        """
        client = self._ensure_client()
        pubsub: PubSub = client.pubsub()
        await pubsub.subscribe(channel)
        logger.info("Subscribed to Redis channel '%s'", channel)
        try:
            async for raw_message in pubsub.listen():
                if raw_message["type"] == "message":
                    data = self._deserialise(raw_message["data"])
                    try:
                        await callback(data)
                    except Exception as exc:
                        logger.exception(
                            "Error in pubsub callback for channel %s: %s", channel, exc
                        )
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ── Utility ───────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            client = self._ensure_client()
            return await client.ping()
        except Exception:
            return False

    async def ttl(self, key: str) -> int:
        """
        Return the remaining TTL of *key* in seconds.

        Returns -1 if the key exists but has no TTL, -2 if the key does not exist.
        """
        client = self._ensure_client()
        return int(await client.ttl(key))
