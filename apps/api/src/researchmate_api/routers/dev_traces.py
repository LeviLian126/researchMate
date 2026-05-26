from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import not_implemented_detail, require_admin
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.trace import DeveloperTrace


router = APIRouter()


# 返回管理员可见的脱敏 Developer Trace。
@router.get("/dev/traces/{trace_id}", response_model=DeveloperTrace)
def get_trace(trace_id: UUID, user: CurrentUser = Depends(require_admin)) -> DeveloperTrace:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("TRACE_GET_NOT_IMPLEMENTED"),
    )

