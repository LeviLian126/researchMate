from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import (
    get_chat_provider,
    get_current_user,
    get_store,
    raise_api_error,
)
from researchmate_api.schemas.common import CurrentUser, ExecutionPlan, TaskType
from researchmate_api.schemas.quiz import QuizHistoryResponse, QuizRequest, QuizResponse
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import build_grounded_answer
from researchmate_api.services.llm import ChatProvider, ProviderRequestError
from researchmate_api.services.quiz_generation import (
    QuizGenerationError,
    generate_llm_quiz_set,
    generate_quiz_set,
)
from researchmate_api.services.retrieval import retrieve_local_chunks
from researchmate_api.services.store import ResearchMateRepository

router = APIRouter()


@router.post("/quiz", response_model=QuizResponse)
def create_quiz(
    payload: QuizRequest,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
    chat_provider: ChatProvider | None = Depends(get_chat_provider),
) -> QuizResponse:
    project = repository.get_project(user, payload.project_id)
    if project is None or project.status != "active":
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    if project.kind != "workspace":
        raise_api_error(
            status.HTTP_404_NOT_FOUND,
            "QUIZ_NOT_AVAILABLE",
            "Quiz is available only inside a project.",
        )
    if not repository.increment_usage(user, "quiz", limit=100):
        raise_api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Daily quiz quota exceeded.",
        )
    chunks = repository.project_chunks(user, payload.project_id)
    if chunks is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    ranked = retrieve_local_chunks(chunks, payload.prompt, limit=len(chunks))
    # Represent every ready source before adding more high-scoring chunks.
    first_by_document = {}
    for candidate in ranked:
        document_key = candidate.document_id or candidate.id
        first_by_document.setdefault(document_key, candidate)
    target = min(50, max(40, len(first_by_document)))
    retrieved = list(first_by_document.values())
    selected_ids = {candidate.id for candidate in retrieved}
    retrieved.extend(
        candidate for candidate in ranked if candidate.id not in selected_ids
    )
    retrieved = retrieved[:target]
    if not retrieved:
        raise_api_error(
            status.HTTP_409_CONFLICT,
            "DOCUMENT_NOT_INDEXED",
            "No ready local document chunks exist for quiz generation.",
        )
    _, citations, _ = build_grounded_answer(payload.prompt, retrieved)
    try:
        if chat_provider is not None:
            quiz_set, _ = generate_llm_quiz_set(
                chat_provider,
                retrieved,
                citations,
                payload.prompt,
                payload.single_choice_count,
                payload.fill_blank_count,
                payload.subjective_count,
            )
        else:
            quiz_set = generate_quiz_set(
                retrieved,
                citations,
                payload.single_choice_count,
                payload.fill_blank_count,
                payload.subjective_count,
            )
    except (ProviderRequestError, QuizGenerationError):
        raise_api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "QUIZ_PROVIDER_UNAVAILABLE",
            "The quiz provider could not produce a validated source-backed quiz.",
        )
    tool_calls = [
        ToolCallTrace(
            id=uuid4(),
            tool_name="query_local_docs",
            input_summary={
                "project_id": str(payload.project_id),
                "query_length": len(payload.prompt),
            },
            output_summary={"chunks": len(retrieved)},
            status="succeeded",
            latency_ms=0,
        ),
        ToolCallTrace(
            id=uuid4(),
            tool_name="generate_quiz",
            input_summary={
                "schema": "QuizSet",
                "requested_questions": (
                    payload.single_choice_count
                    + payload.fill_blank_count
                    + payload.subjective_count
                ),
            },
            output_summary={"questions": len(quiz_set.questions)},
            status="succeeded",
            latency_ms=0,
        ),
    ]
    plan = ExecutionPlan(
        task_type=TaskType.QUIZ,
        allowed_tools=["query_local_docs", "generate_quiz"],
        requires_local_docs=True,
        requires_web=False,
        context_strategy="quiz",
        output_schema="QuizSet",
    )
    validation_result = {
        "passed": len(quiz_set.questions) > 0,
        "question_count": len(quiz_set.questions),
    }
    run_id, trace_id = repository.record_run(
        user=user,
        project_id=payload.project_id,
        message=payload.prompt,
        plan=plan,
        router_reason="Quiz uses local document retrieval.",
        retrieved_chunks=retrieved,
        citations=citations,
        tool_calls=tool_calls,
        validation_result=validation_result,
    )
    repository.save_quiz_set(user, payload.project_id, run_id, quiz_set)
    return QuizResponse(
        quiz_set=quiz_set,
        run_id=run_id,
        trace_id=trace_id,
        validation_status="passed" if validation_result["passed"] else "failed",
    )


@router.get("/projects/{project_id}/quiz", response_model=QuizHistoryResponse)
def list_quiz_history(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    repository: ResearchMateRepository = Depends(get_store),
) -> QuizHistoryResponse:
    quiz_sets = repository.list_quiz_sets(user, project_id)
    if quiz_sets is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return QuizHistoryResponse(project_id=project_id, quiz_sets=quiz_sets)
