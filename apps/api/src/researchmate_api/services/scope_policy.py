"""Define workspace and personal-conversation scope rules for every interface."""

from __future__ import annotations

from researchmate_api.schemas.project import ProjectRecord


class ProjectScopeError(ValueError):
    """Describe a capability that requires an explicit conversation scope."""

    code = "PROJECT_SCOPE_REQUIRES_CONVERSATION"


def require_workspace_scope(project: ProjectRecord) -> None:
    """Reject project-wide access to the shared personal-project container."""
    if project.kind != "workspace":
        raise ProjectScopeError(
            "Personal chat data must be accessed through an owned conversation scope."
        )
