"""FastAPI dependency functions for authentication and permission checking."""
from __future__ import annotations

import logging
import uuid
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from security.auth.api_key_manager import api_key_manager
from security.auth.jwt_handler import jwt_handler
from security.rbac.role_manager import Permission, Role, role_manager
from storage.database.postgres import get_async_session
from storage.database.postgres.models import User
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Optional bearer scheme – we handle the 401 ourselves for better messages.
_bearer_scheme = HTTPBearer(auto_error=False)


class PermissionChecker:
    """
    Reusable FastAPI dependency factory for permission and role enforcement.

    Usage::

        @router.get("/secure")
        async def secure_route(user: User = Depends(require_permission(Permission.ENTITY_READ))):
            ...
    """

    def require_permission(self, permission: Permission) -> Callable:
        """
        Return a FastAPI dependency that enforces a specific permission.

        The dependency resolves ``get_current_user`` internally, so it can be
        used directly in route signatures.
        """
        async def _dependency(
            current_user: User = Depends(get_current_user),
        ) -> User:
            try:
                role = Role(current_user.role)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unknown role: {current_user.role}",
                )
            if not role_manager.has_permission(role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value} is required",
                )
            return current_user

        # Give the dependency a meaningful name for OpenAPI introspection.
        _dependency.__name__ = f"require_{permission.value.replace(':', '_')}"
        return _dependency

    def require_role(self, minimum_role: Role) -> Callable:
        """
        Return a FastAPI dependency that enforces a minimum role level.

        Roles are compared by their hierarchy level (admin > analyst > viewer > api_user).
        """
        async def _dependency(
            current_user: User = Depends(get_current_user),
        ) -> User:
            try:
                user_role = Role(current_user.role)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unknown role: {current_user.role}",
                )
            if not role_manager.is_at_least(user_role, minimum_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Role {minimum_role.value!r} or higher is required; "
                        f"you have {user_role.value!r}"
                    ),
                )
            return current_user

        _dependency.__name__ = f"require_role_{minimum_role.value}"
        return _dependency

    def check_permission(self, user: User, permission: Permission) -> bool:
        """Programmatic (non-dependency) permission check for use inside route handlers."""
        try:
            role = Role(user.role)
        except ValueError:
            return False
        return role_manager.has_permission(role, permission)

    def check_role(self, user: User, minimum_role: Role) -> bool:
        """Programmatic (non-dependency) role-level check."""
        try:
            role = Role(user.role)
        except ValueError:
            return False
        return role_manager.is_at_least(role, minimum_role)


# Module-level singleton.
permission_checker = PermissionChecker()


async def _get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Fetch an active user by primary key."""
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """
    FastAPI dependency: resolve the current authenticated user.

    Supports two authentication mechanisms (checked in order):
    1. ``Authorization: Bearer <jwt>`` header.
    2. ``X-API-Key: osint_<hex>`` header.

    Raises
    ------
    HTTPException 401
        If no valid credentials are found or the token/key is invalid.
    HTTPException 403
        If the account is disabled.
    """
    # ── 1. Try JWT Bearer token ───────────────────────────────────────────────
    if credentials is not None and credentials.credentials:
        payload = jwt_handler.verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Expected an access token, got a refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await _get_user_by_id(session, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or account deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # ── 2. Try X-API-Key header ───────────────────────────────────────────────
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        api_key_obj = await api_key_manager.validate_api_key(session, api_key_header)
        if api_key_obj is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )
        # Update last-used asynchronously (best-effort, same session).
        await api_key_manager.update_last_used(session, api_key_obj.id)

        user = await _get_user_by_id(session, api_key_obj.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key owner not found or account deactivated",
            )
        return user

    # ── 3. No credentials ─────────────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """
    FastAPI dependency: resolve the current user if authenticated, or return ``None``.

    Useful for endpoints that behave differently for anonymous vs. authenticated callers.
    """
    # JWT Bearer
    if credentials is not None and credentials.credentials:
        payload = jwt_handler.verify_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            try:
                user_id = uuid.UUID(payload["sub"])
                return await _get_user_by_id(session, user_id)
            except (ValueError, KeyError):
                return None

    # API Key
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        api_key_obj = await api_key_manager.validate_api_key(session, api_key_header)
        if api_key_obj:
            await api_key_manager.update_last_used(session, api_key_obj.id)
            return await _get_user_by_id(session, api_key_obj.user_id)

    return None


def require_permission(permission: Permission) -> Callable:
    """Module-level shortcut for ``permission_checker.require_permission``."""
    return permission_checker.require_permission(permission)


def require_role(minimum_role: Role) -> Callable:
    """Module-level shortcut for ``permission_checker.require_role``."""
    return permission_checker.require_role(minimum_role)
