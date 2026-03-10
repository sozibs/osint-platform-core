"""Pydantic models for user-related request and response payloads."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")
_VALID_ROLES = {"admin", "analyst", "viewer", "api_user"}


class UserCreate(BaseModel):
    """Payload for creating a new user account."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Alphanumeric username with underscores (3-50 characters)",
    )
    email: EmailStr = Field(..., description="Valid e-mail address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters)",
    )
    role: str = Field(
        default="viewer",
        description="One of: admin, analyst, viewer, api_user",
    )

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-50 characters and contain only letters, digits, "
                "and underscores"
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(f"role must be one of: {sorted(_VALID_ROLES)}")
        return v

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, one lowercase "
                "letter, and one digit"
            )
        return v


class UserUpdate(BaseModel):
    """Payload for partial user profile updates."""

    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-50 characters and contain only letters, digits, "
                "and underscores"
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_ROLES:
            raise ValueError(f"role must be one of: {sorted(_VALID_ROLES)}")
        return v


class UserResponse(BaseModel):
    """Serialized user object returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserLogin(BaseModel):
    """Credentials for username/password authentication."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access + refresh token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class TokenRefresh(BaseModel):
    """Payload for the token-refresh endpoint."""

    refresh_token: str
