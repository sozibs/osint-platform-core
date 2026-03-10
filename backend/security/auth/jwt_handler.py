"""JWT token creation, verification, and refresh logic."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """Handles JWT creation, verification, and password hashing."""

    def __init__(self) -> None:
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    def create_access_token(
        self,
        subject: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a signed JWT access token.

        Parameters
        ----------
        subject:
            The user ID (UUID as string) stored in the ``sub`` claim.
        additional_claims:
            Optional extra claims merged into the payload (e.g. ``role``).

        Returns
        -------
        str
            Encoded JWT string.
        """
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": subject,
            "type": "access",
            "iat": now,
            "exp": now + self.access_token_expire,
        }
        if additional_claims:
            payload.update(additional_claims)
        try:
            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        except Exception as exc:
            logger.error("Failed to create access token for subject %s: %s", subject, exc)
            raise

    def create_refresh_token(self, subject: str) -> str:
        """
        Create a signed JWT refresh token.

        Refresh tokens carry only the ``sub`` claim (no role) so that the
        role is always re-read from the database on refresh.

        Parameters
        ----------
        subject:
            The user ID (UUID as string).

        Returns
        -------
        str
            Encoded JWT string.
        """
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": subject,
            "type": "refresh",
            "iat": now,
            "exp": now + self.refresh_token_expire,
        }
        try:
            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        except Exception as exc:
            logger.error("Failed to create refresh token for subject %s: %s", subject, exc)
            raise

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and verify a JWT token.

        Parameters
        ----------
        token:
            The encoded JWT string.

        Returns
        -------
        Optional[Dict[str, Any]]
            The decoded payload dict, or ``None`` if the token is invalid /
            expired / tampered.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            # Validate required claims are present
            if "sub" not in payload or "type" not in payload:
                logger.warning("JWT missing required claims: %s", list(payload.keys()))
                return None
            return payload
        except JWTError as exc:
            logger.warning("JWT verification failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Unexpected error during JWT verification: %s", exc)
            return None

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against its bcrypt hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_token_expiry_seconds(self, token_type: str = "access") -> int:
        """Return the configured token lifetime in seconds."""
        if token_type == "refresh":
            return int(self.refresh_token_expire.total_seconds())
        return int(self.access_token_expire.total_seconds())


# Module-level singleton used across the application.
jwt_handler = JWTHandler()
