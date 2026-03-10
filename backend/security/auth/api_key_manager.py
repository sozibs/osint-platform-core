"""API key generation, hashing, validation, and lifecycle management."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database.postgres.models import ApiKey

logger = logging.getLogger(__name__)

# Prefix applied to every raw API key so callers can quickly identify them.
_KEY_PREFIX = "osint_"
_KEY_BYTES = 32  # 32 random bytes → 64-char hex string → total ~71 chars with prefix


def generate_api_key() -> str:
    """
    Generate a cryptographically-secure raw API key.

    Format: ``osint_<64-char hex>``

    Returns
    -------
    str
        The raw (unhashed) key that must be shown to the user exactly once.
    """
    return f"{_KEY_PREFIX}{secrets.token_hex(_KEY_BYTES)}"


def hash_api_key(key: str) -> str:
    """
    Compute the SHA-256 hash of a raw API key.

    The hash (not the raw key) is stored in the database.

    Parameters
    ----------
    key:
        Raw API key string.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_api_key(key: str, key_hash: str) -> bool:
    """
    Compare a raw key against its stored SHA-256 hash using a
    constant-time comparison to prevent timing attacks.

    Parameters
    ----------
    key:
        The raw API key provided by the caller.
    key_hash:
        The stored SHA-256 hash to compare against.

    Returns
    -------
    bool
        ``True`` if the key matches the hash.
    """
    computed = hash_api_key(key)
    return secrets.compare_digest(computed, key_hash)


class APIKeyManager:
    """High-level async manager for API key operations backed by PostgreSQL."""

    async def create_api_key(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        name: str,
        permissions: List[str],
        expires_at: Optional[datetime] = None,
    ) -> tuple[ApiKey, str]:
        """
        Generate and persist a new API key.

        The raw key is returned alongside the ORM object so that callers can
        present it to the user once (it is not stored in plain text).

        Parameters
        ----------
        session:
            Active async SQLAlchemy session.
        user_id:
            Owner of the API key.
        name:
            Human-readable label for the key.
        permissions:
            List of permission strings granted to this key.
        expires_at:
            Optional UTC expiry timestamp.

        Returns
        -------
        tuple[ApiKey, str]
            ``(orm_object, raw_key)`` — persist the ORM object, show the raw key.
        """
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)

        api_key = ApiKey(
            key_hash=key_hash,
            name=name,
            user_id=user_id,
            permissions=permissions,
            expires_at=expires_at,
            is_active=True,
        )
        session.add(api_key)
        await session.flush()  # Populate server-generated fields (id, created_at)
        await session.refresh(api_key)
        logger.info("Created API key %s for user %s", api_key.id, user_id)
        return api_key, raw_key

    async def validate_api_key(
        self,
        session: AsyncSession,
        raw_key: str,
    ) -> Optional[ApiKey]:
        """
        Look up and validate a raw API key against the database.

        Validates:
        - Key exists and is active.
        - Key has not expired.

        Parameters
        ----------
        session:
            Active async SQLAlchemy session.
        raw_key:
            The raw key string sent by the caller.

        Returns
        -------
        Optional[ApiKey]
            The ``ApiKey`` ORM object if valid, else ``None``.
        """
        key_hash = hash_api_key(raw_key)
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            return None

        # Check expiry
        if api_key.expires_at is not None:
            now = datetime.now(timezone.utc)
            expires = api_key.expires_at
            # Ensure timezone-aware comparison
            if expires.tzinfo is None:
                from datetime import timezone as tz
                expires = expires.replace(tzinfo=tz.utc)
            if now > expires:
                logger.info("API key %s has expired", api_key.id)
                return None

        return api_key

    async def revoke_api_key(
        self,
        session: AsyncSession,
        api_key_id: uuid.UUID,
    ) -> bool:
        """
        Deactivate an API key by ID.

        Parameters
        ----------
        session:
            Active async SQLAlchemy session.
        api_key_id:
            Primary key of the ``ApiKey`` record.

        Returns
        -------
        bool
            ``True`` if a row was updated; ``False`` if the key was not found.
        """
        result = await session.execute(
            sql_update(ApiKey)
            .where(ApiKey.id == api_key_id)
            .values(is_active=False)
            .returning(ApiKey.id)
        )
        row = result.first()
        if row is None:
            logger.warning("Attempted to revoke non-existent API key %s", api_key_id)
            return False
        logger.info("Revoked API key %s", api_key_id)
        return True

    async def list_user_api_keys(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[ApiKey]:
        """
        Return all API keys belonging to a user, ordered by creation date desc.

        Parameters
        ----------
        session:
            Active async SQLAlchemy session.
        user_id:
            The user whose keys should be listed.

        Returns
        -------
        List[ApiKey]
            Possibly-empty list of ``ApiKey`` ORM objects.
        """
        result = await session.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_last_used(
        self,
        session: AsyncSession,
        api_key_id: uuid.UUID,
    ) -> None:
        """
        Update the ``last_used_at`` timestamp for an API key.

        This is a best-effort fire-and-forget operation; errors are logged
        but not propagated.

        Parameters
        ----------
        session:
            Active async SQLAlchemy session.
        api_key_id:
            Primary key of the ``ApiKey`` record.
        """
        try:
            await session.execute(
                sql_update(ApiKey)
                .where(ApiKey.id == api_key_id)
                .values(last_used_at=datetime.now(timezone.utc))
            )
        except Exception as exc:
            logger.warning("Failed to update last_used_at for API key %s: %s", api_key_id, exc)


# Module-level singleton.
api_key_manager = APIKeyManager()
