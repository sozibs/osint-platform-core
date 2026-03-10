"""Role-based access control definitions and role manager."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set


class Role(str, Enum):
    """Platform roles ordered from least to most privileged."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(str, Enum):
    """Fine-grained permissions assignable to roles and API keys."""

    # Entity permissions
    ENTITY_READ = "entity:read"
    ENTITY_CREATE = "entity:create"
    ENTITY_UPDATE = "entity:update"
    ENTITY_DELETE = "entity:delete"

    # Relationship permissions
    RELATIONSHIP_READ = "relationship:read"
    RELATIONSHIP_CREATE = "relationship:create"
    RELATIONSHIP_UPDATE = "relationship:update"
    RELATIONSHIP_DELETE = "relationship:delete"

    # Case permissions
    CASE_READ = "case:read"
    CASE_CREATE = "case:create"
    CASE_UPDATE = "case:update"
    CASE_DELETE = "case:delete"

    # Source / ingestion permissions
    SOURCE_READ = "source:read"
    SOURCE_CREATE = "source:create"
    SOURCE_DELETE = "source:delete"
    INGEST = "ingest:create"

    # Search
    SEARCH = "search:read"

    # Export
    EXPORT = "export:create"

    # Administration
    USER_MANAGE = "user:manage"
    API_KEY_MANAGE = "apikey:manage"
    SYSTEM_ADMIN = "system:admin"

    # Graph analytics
    GRAPH_READ = "graph:read"
    GRAPH_ANALYZE = "graph:analyze"


# Full set of all permissions – used to grant admin all permissions.
_ALL_PERMISSIONS: Set[Permission] = set(Permission)

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: _ALL_PERMISSIONS,
    Role.ANALYST: {
        Permission.ENTITY_READ,
        Permission.ENTITY_CREATE,
        Permission.ENTITY_UPDATE,
        Permission.RELATIONSHIP_READ,
        Permission.RELATIONSHIP_CREATE,
        Permission.RELATIONSHIP_UPDATE,
        Permission.CASE_READ,
        Permission.CASE_CREATE,
        Permission.CASE_UPDATE,
        Permission.SOURCE_READ,
        Permission.INGEST,
        Permission.SEARCH,
        Permission.EXPORT,
        Permission.GRAPH_READ,
        Permission.GRAPH_ANALYZE,
        Permission.API_KEY_MANAGE,
    },
    Role.VIEWER: {
        Permission.ENTITY_READ,
        Permission.RELATIONSHIP_READ,
        Permission.CASE_READ,
        Permission.SOURCE_READ,
        Permission.SEARCH,
        Permission.GRAPH_READ,
    },
    Role.API_USER: {
        Permission.ENTITY_READ,
        Permission.RELATIONSHIP_READ,
        Permission.SEARCH,
        Permission.GRAPH_READ,
    },
}

# Numeric hierarchy: higher value = more privileged.
_ROLE_LEVELS: Dict[Role, int] = {
    Role.ADMIN: 4,
    Role.ANALYST: 3,
    Role.VIEWER: 2,
    Role.API_USER: 1,
}


class RoleManager:
    """Utility class for querying the RBAC configuration."""

    def get_permissions(self, role: Role) -> Set[Permission]:
        """Return the set of permissions granted to *role*."""
        return ROLE_PERMISSIONS.get(role, set())

    def has_permission(self, role: Role, permission: Permission) -> bool:
        """Return ``True`` if *role* includes *permission*."""
        return permission in self.get_permissions(role)

    def get_all_roles(self) -> List[Role]:
        """Return all defined roles."""
        return list(Role)

    def role_hierarchy_level(self, role: Role) -> int:
        """
        Return the numeric hierarchy level of *role*.

        Higher values indicate more privileged roles:
        admin=4, analyst=3, viewer=2, api_user=1.
        """
        return _ROLE_LEVELS.get(role, 0)

    def is_at_least(self, role: Role, minimum: Role) -> bool:
        """Return ``True`` if *role* is at least as privileged as *minimum*."""
        return self.role_hierarchy_level(role) >= self.role_hierarchy_level(minimum)

    def role_from_string(self, role_str: str) -> Role:
        """
        Convert a string to a ``Role`` enum value.

        Raises
        ------
        ValueError
            If *role_str* does not correspond to a valid role.
        """
        try:
            return Role(role_str)
        except ValueError:
            valid = [r.value for r in Role]
            raise ValueError(f"Invalid role {role_str!r}. Valid roles: {valid}")


# Module-level singleton.
role_manager = RoleManager()
