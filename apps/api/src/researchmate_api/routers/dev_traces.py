"""Expose the privileged HTTP endpoint for redacted developer traces."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_store, raise_api_error, require_admin
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.trace import DeveloperTrace
from researchmate_api.services.access_policy import TraceAccessError, TraceQueryService
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.get("/dev/traces/{trace_id}", response_model=DeveloperTrace)
def get_trace(
    trace_id: UUID,
    user: CurrentUser = Depends(require_admin),
    repository: ResearchMateRepository = Depends(get_store),
) -> DeveloperTrace:
    """Return one trace through the same role policy used by MCP."""
    try:
        trace = TraceQueryService(repository).get(user, trace_id)
    except TraceAccessError:
        raise_api_error(status.HTTP_403_FORBIDDEN, "ADMIN_REQUIRED", "Trace is admin-only.")
    if trace is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "TRACE_NOT_FOUND", "Trace was not found.")
    return trace
