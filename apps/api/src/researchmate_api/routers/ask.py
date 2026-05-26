from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import CurrentUser


router = APIRouter()


# 接收 Ask 请求并返回结构化回答。
@router.post("/ask", response_model=AskResponse)
def ask(_: AskRequest, user: CurrentUser = Depends(get_current_user)) -> AskResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("ASK_NOT_IMPLEMENTED"),
    )

