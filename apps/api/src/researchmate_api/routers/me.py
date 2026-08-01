"""Expose the authenticated caller's public identity summary."""

from fastapi import APIRouter, Depends

from researchmate_api.dependencies import get_current_user
from researchmate_api.schemas.common import CurrentUser

router = APIRouter()


# 返回当前登录用户摘要。
@router.get("/me", response_model=CurrentUser)
def get_me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Return the identity established by the authentication dependency."""
    return user
