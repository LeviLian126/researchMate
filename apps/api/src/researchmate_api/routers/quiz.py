from fastapi import APIRouter, Depends, HTTPException, status

from researchmate_api.dependencies import get_current_user, not_implemented_detail
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.quiz import QuizRequest, QuizResponse


router = APIRouter()


# 接收 Quiz 请求并返回结构化测验。
@router.post("/quiz", response_model=QuizResponse)
def create_quiz(_: QuizRequest, user: CurrentUser = Depends(get_current_user)) -> QuizResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=not_implemented_detail("QUIZ_NOT_IMPLEMENTED"),
    )

