"""Centralize application-level authorization shared by HTTP and MCP interfaces."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.trace import DeveloperTrace
from researchmate_api.services.store import ResearchMateRepository


class TraceAccessError(PermissionError):
    """Represent a denied developer-trace request without transport-specific details."""

    code = "ADMIN_REQUIRED"


class TraceQueryService:
    """Apply the developer/admin trace policy before loading trace data."""

    def __init__(self, repository: ResearchMateRepository) -> None:
        """Bind the repository used after the caller passes the role gate."""
        self.repository = repository

    def get(self, user: CurrentUser, trace_id: UUID) -> DeveloperTrace | None:
        """Return a trace only to developer or admin identities."""
        if user.role not in {"developer", "admin"}:
            raise TraceAccessError("Developer traces require a privileged role.")
        return self.repository.get_trace(user, trace_id)
