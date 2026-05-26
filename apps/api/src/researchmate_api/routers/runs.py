from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.sources import RunSourcesResponse


router = APIRouter()


# 返回一次运行的 Sources panel 数据。
@router.get("/runs/{run_id}/sources", response_model=RunSourcesResponse)
def get_run_sources(run_id: UUID, user: CurrentUser = Depends(get_current_user)) -> RunSourcesResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("RUN_SOURCES_NOT_IMPLEMENTED"),
    )

