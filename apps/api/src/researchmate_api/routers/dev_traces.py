from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import raise_api_error, require_admin
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.trace import DeveloperTrace
from researchmate_api.services.store import store


router = APIRouter()


# 返回管理员可见的脱敏 Developer Trace。
@router.get("/dev/traces/{trace_id}", response_model=DeveloperTrace)
def get_trace(trace_id: UUID, user: CurrentUser = Depends(require_admin)) -> DeveloperTrace:
    trace = store.get_trace(trace_id)
    if trace is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "TRACE_NOT_FOUND", "Trace was not found.")
    if user.role == "developer" or trace.user_id == user.id:
        return trace
    if user.role == "admin":
        return trace
    raise_api_error(status.HTTP_403_FORBIDDEN, "ADMIN_REQUIRED", "Trace is admin-only.")
    raise RuntimeError("unreachable")
