"""Pydantic models for role and permission metadata."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class RoleInfo(BaseModel):
    """Metadata about a platform role."""

    name: str = Field(..., description="Role identifier, e.g. 'analyst'")
    permissions: List[str] = Field(..., description="List of permission strings for this role")
    description: str = Field(..., description="Human-readable description of the role")


class PermissionCheck(BaseModel):
    """Result of a programmatic permission check."""

    permission: str = Field(..., description="The permission that was checked")
    allowed: bool = Field(..., description="Whether the permission is granted")
    reason: str = Field(..., description="Explanation of the decision")


# Static descriptions for each role – referenced by the /roles endpoints.
ROLE_DESCRIPTIONS: dict[str, str] = {
    "admin": (
        "Full system access including user management, system configuration, "
        "and all data operations."
    ),
    "analyst": (
        "Can create, read, and update entities, relationships, and cases. "
        "Can ingest data, run searches, and export results."
    ),
    "viewer": (
        "Read-only access to entities, relationships, cases, sources, and search. "
        "Cannot modify any data."
    ),
    "api_user": (
        "Programmatic read-only access to entities, relationships, and search. "
        "Intended for machine-to-machine integrations."
    ),
}
