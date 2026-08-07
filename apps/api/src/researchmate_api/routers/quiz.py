"""Map HTTP Quiz requests to the shared Quiz application service."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header

from researchmate_api.dependencies import (
    get_chat_provider,
    get_current_user,
    get_store,
    raise_api_error,
)
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.quiz import QuizHistoryResponse, QuizRequest, QuizResponse
from researchmate_api.services.idempotency import IdempotencyCoordinator, IdempotencyError
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.quiz_service import QuizService, QuizServiceError
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.post("/quiz", response_model=QuizResponse)
def create_quiz(
    payload: QuizRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    chat_provider: ChatProvider | None = Depends(get_chat_provider),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=8, max_length=160
    ),
) -> QuizResponse:
    """Generate one source-backed Quiz through the application service."""
    coordinator = IdempotencyCoordinator(repository, user, "quiz", idempotency_key, payload)
    try:
        replay = coordinator.begin()
        if replay is not None:
            return QuizResponse.model_validate(replay)
        response = QuizService(repository, chat_provider).create(user, payload)
        coordinator.complete(response)
        return response
    except IdempotencyError as exc:
        raise_api_error(409, exc.code, exc.message)
    except QuizServiceError as exc:
        coordinator.abandon()
        raise_api_error(exc.status_code, exc.code, exc.message)
    except Exception:
        coordinator.abandon()
        raise


@router.get("/projects/{project_id}/quiz", response_model=QuizHistoryResponse)
def list_quiz_history(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> QuizHistoryResponse:
    """List saved Quiz sets for one owned workspace."""
    quiz_sets = repository.list_quiz_sets(user, project_id)
    if quiz_sets is None:
        raise_api_error(404, "PROJECT_NOT_FOUND", "Project was not found.")
    return QuizHistoryResponse(project_id=project_id, quiz_sets=quiz_sets)
