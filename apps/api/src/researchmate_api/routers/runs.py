from uuid import UUID

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, get_store, raise_api_error
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.services.store import ResearchMateRepository


router = APIRouter()


# 返回一次运行的 Sources panel 数据。
@router.get("/runs/{run_id}/sources", response_model=RunSourcesResponse)
def get_run_sources(
    run_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> RunSourcesResponse:
    response = repository.get_run_sources(user, run_id)
    if response is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "RUN_NOT_FOUND", "Run was not found.")
    return response
