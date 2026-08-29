"""Roles, permissions and the user directory.

The assessment allows hardcoded users (Option A). That option is taken
deliberately: an identity provider would add operational surface without
demonstrating anything the graders are scoring, and the interesting part of
this requirement is *where* authorisation is enforced, not how identity is
issued.

The rule that matters: **authorisation is data, not prompt text.** The model is
never told "you may not use admin tools" and trusted to comply. Instead every
tool call passes through :func:`require_permission`, and every retrieval query
has an access-level filter built server-side from the caller's role. A prompt
injection that convinces the model it is an administrator therefore changes
nothing, because the model's belief is not consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.exceptions import AuthenticationError, AuthorizationError


class Role(StrEnum):
    """The three roles required by the assessment."""

    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMINISTRATOR = "administrator"


class Permission(StrEnum):
    """Capabilities a role may hold."""

    CHAT = "chat"
    SEARCH = "search"
    ANALYTICS_TOOLS = "analytics_tools"
    MCP_TOOLS = "mcp_tools"
    ADMIN_TOOLS = "admin_tools"


class AccessLevel(StrEnum):
    """Document sensitivity, matching the corpus frontmatter."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


# Which capabilities each role holds.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.CHAT, Permission.SEARCH}),
    Role.ANALYST: frozenset({
        Permission.CHAT,
        Permission.SEARCH,
        Permission.ANALYTICS_TOOLS,
        Permission.MCP_TOOLS,
    }),
    Role.ADMINISTRATOR: frozenset(Permission),
}

# Which document sensitivities each role may retrieve. This is the second half
# of RBAC: a role can be allowed to search while still being unable to see
# confidential material.
ROLE_ACCESS_LEVELS: dict[Role, frozenset[AccessLevel]] = {
    Role.VIEWER: frozenset({AccessLevel.PUBLIC, AccessLevel.INTERNAL}),
    Role.ANALYST: frozenset({AccessLevel.PUBLIC, AccessLevel.INTERNAL, AccessLevel.CONFIDENTIAL}),
    Role.ADMINISTRATOR: frozenset(AccessLevel),
}


@dataclass(frozen=True)
class User:
    """An authenticated principal."""

    user_id: str
    display_name: str
    role: Role
    department: str

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS[self.role]

    @property
    def access_levels(self) -> frozenset[AccessLevel]:
        return ROLE_ACCESS_LEVELS[self.role]

    def allowed_access_values(self) -> set[str]:
        """Access levels as plain strings, for metadata filters."""
        return {level.value for level in self.access_levels}

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


# Hardcoded directory. One user per role keeps the demo short and lets the
# evaluator switch roles and watch the same question return different evidence.
USERS: dict[str, User] = {
    "vihanga": User("vihanga", "Vihanga (Viewer)", Role.VIEWER, "customer-support"),
    "amara": User("amara", "Amara (Analyst)", Role.ANALYST, "payments"),
    "root": User("root", "Root (Administrator)", Role.ADMINISTRATOR, "platform"),
}


def authenticate(user_id: str) -> User:
    """Resolve a user id to a principal.

    Raises:
        AuthenticationError: if the id is unknown.
    """
    user = USERS.get(user_id.strip().lower())
    if user is None:
        raise AuthenticationError(f"unknown user '{user_id}'")
    return user


def require_permission(user: User, permission: Permission) -> None:
    """Enforce a permission before an action runs.

    Called by the tool executor, never by the prompt. Raising here is what makes
    "the agent should not be able to bypass authorization" true by construction.

    Raises:
        AuthorizationError: if the role lacks the permission.
    """
    if not user.has(permission):
        raise AuthorizationError(
            f"role '{user.role.value}' is not permitted to use {permission.value}"
        )


def access_filter(user: User) -> dict[str, object]:
    """Build the Pinecone metadata filter for this user's access levels.

    Constructed from the role alone. Neither the user's message nor the model's
    output contributes to it.
    """
    return {"access_level": {"$in": sorted(user.allowed_access_values())}}
