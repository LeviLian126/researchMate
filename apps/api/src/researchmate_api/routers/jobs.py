from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, raise_api_error
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.job import JobRecord
from researchmate_api.services.store import store


router = APIRouter()


# 查询异步任务状态。
@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: UUID, user: CurrentUser = Depends(get_current_user)) -> JobRecord:
    job = store.get_job(user, job_id)
    if job is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Job was not found.")
    return job
