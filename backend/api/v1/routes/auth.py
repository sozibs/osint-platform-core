"""
Authentication router.

Provides JWT-based authentication with refresh tokens and API key management.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from storage.database.postgres import get_async_session
from storage.database.postgres.models import ApiKey, User
from storage.database.postgres.queries import (
    create_record,
    exists_by_field,
    get_by_id,
    get_all,
)

router = APIRouter(prefix="/auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="viewer")


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    permissions: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    key: Optional[str] = None  # Only set on creation


# ── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Validate the Bearer JWT and return the authenticated User."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        token_type: str = payload.get("type", "access")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an access token",
        )

    user = await get_by_id(session, User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Register a new user account."""
    if await exists_by_field(session, User, "username", body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    if await exists_by_field(session, User, "email", body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await create_record(
        session,
        User,
        {
            "username": body.username,
            "email": body.email,
            "hashed_password": hash_password(body.password),
            "role": body.role if body.role in {"viewer", "analyst", "admin"} else "viewer",
        },
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Authenticate with username + password and receive JWT tokens."""
    users = await get_all(session, User, filters={"username": form_data.username})
    user = users[0] if users else None

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # Update last_login
    from sqlalchemy import update as sql_update
    await session.execute(
        sql_update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.now(timezone.utc))
    )

    access_token = create_token(
        {"sub": str(user.id), "type": "access", "role": user.role},
        timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    refresh_token = create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {exc}")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user = await get_by_id(session, User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_token(
        {"sub": str(user.id), "type": "access", "role": user.role},
        timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    new_refresh = create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKeyResponse:
    """Generate a new API key for the authenticated user."""
    raw_key = f"osint_{secrets.token_urlsafe(40)}"
    key_hash = hash_api_key(raw_key)
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    api_key = await create_record(
        session,
        ApiKey,
        {
            "key_hash": key_hash,
            "name": body.name,
            "user_id": current_user.id,
            "permissions": body.permissions,
            "expires_at": expires_at,
        },
    )
    response = ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        permissions=api_key.permissions or [],
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        key=raw_key,  # Only returned once
    )
    return response


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> List[ApiKeyResponse]:
    """List all API keys belonging to the authenticated user."""
    keys = await get_all(session, ApiKey, filters={"user_id": current_user.id})
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            permissions=k.permissions or [],
            is_active=k.is_active,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Revoke (deactivate) an API key."""
    key = await get_by_id(session, ApiKey, key_id)
    if key is None or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    from sqlalchemy import update as sql_update
    await session.execute(
        sql_update(ApiKey).where(ApiKey.id == key_id).values(is_active=False)
    )
