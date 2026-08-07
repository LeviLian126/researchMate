"""Expose the authenticated caller's public identity summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from researchmate_api.dependencies import get_current_user
from researchmate_api.schemas.common import CurrentUser

router = APIRouter()


# Return the currently logged-in user summary.
@router.get("/me", response_model=CurrentUser)
def get_me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Return the identity established by the authentication dependency."""
    return user
