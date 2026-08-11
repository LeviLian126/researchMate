"""Expose owner feedback and privileged Bad Case review operations."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from researchmate_api.dependencies import (
    get_current_user,
    get_evidence_store,
    raise_api_error,
    require_admin,
)
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.feedback import (
    AnswerFeedbackListResponse,
    AnswerFeedbackRecord,
    AnswerFeedbackUpsert,
    FeedbackPromotionCreate,
    FeedbackPromotionResult,
    FeedbackRating,
)
from researchmate_api.services.evidence_faults import EvidenceStoreError
from researchmate_api.services.evidence_store import EvidenceRepository

router = APIRouter()


def _feedback_store_call[ResultT](callback: Callable[[], ResultT]) -> ResultT:
    """Map feedback-store errors into the shared public API envelope."""
    try:
        return callback()
    except EvidenceStoreError as exc:
        raise_api_error(exc.status_code, exc.code, exc.code.replace("_", " ").title())


@router.put("/answer-feedback/{ask_run_id}", response_model=AnswerFeedbackRecord)
def upsert_answer_feedback(
    ask_run_id: UUID,
    payload: AnswerFeedbackUpsert,
    user: CurrentUser = Depends(get_current_user),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> AnswerFeedbackRecord:
    """Create or replace feedback for one caller-owned persisted answer."""
    record = _feedback_store_call(
        lambda: evidence.upsert_answer_feedback(user, ask_run_id, payload)
    )
    if record is None:
        raise_api_error(404, "ANSWER_RUN_NOT_FOUND", "Answer run was not found.")
    return record


@router.get(
    "/projects/{project_id}/answer-feedback",
    response_model=AnswerFeedbackListResponse,
)
def list_answer_feedback(
    project_id: UUID,
    rating: FeedbackRating | None = Query(default=None),
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> AnswerFeedbackListResponse:
    """List the developer's bounded owner-scoped feedback review queue."""
    records = evidence.list_answer_feedback(user, project_id, rating)
    if records is None:
        raise_api_error(404, "PROJECT_NOT_FOUND", "Project was not found.")
    return records


@router.post(
    "/answer-feedback/{feedback_id}/promote",
    response_model=FeedbackPromotionResult,
    status_code=status.HTTP_201_CREATED,
)
def promote_answer_feedback(
    feedback_id: UUID,
    payload: FeedbackPromotionCreate,
    user: CurrentUser = Depends(require_admin),
    evidence: EvidenceRepository = Depends(get_evidence_store),
) -> FeedbackPromotionResult:
    """Promote reviewed feedback into the next frozen regression dataset version."""
    result = _feedback_store_call(
        lambda: evidence.promote_answer_feedback(user, feedback_id, payload)
    )
    if result is None:
        raise_api_error(404, "ANSWER_FEEDBACK_NOT_FOUND", "Answer feedback was not found.")
    return result
