from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.job import JobRecord


router = APIRouter()


# 查询异步任务状态。
@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: UUID, user: CurrentUser = Depends(get_current_user)) -> JobRecord:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("JOB_GET_NOT_IMPLEMENTED"),
    )

