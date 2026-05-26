from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, raise_api_error
from researchmate_api.schemas.common import CurrentUser, SourceMode, TaskType
from researchmate_api.schemas.quiz import QuizHistoryResponse, QuizRequest, QuizResponse
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import build_grounded_answer
from researchmate_api.services.quiz_generation import generate_quiz_set
from researchmate_api.services.retrieval import retrieve_local_chunks
from researchmate_api.services.source_policy import resolve_intent, validate_tool_policy
from researchmate_api.services.store import store


router = APIRouter()


# 接收 Quiz 请求并返回结构化测验。
@router.post("/quiz", response_model=QuizResponse)
def create_quiz(payload: QuizRequest, user: CurrentUser = Depends(get_current_user)) -> QuizResponse:
    if store.get_project(user, payload.project_id) is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    if not store.increment_usage(user, "quiz", limit=100):
        raise_api_error(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", "Daily quiz quota exceeded.")
    selected_mode = SourceMode(payload.selected_mode)
    intent = resolve_intent(payload.prompt, selected_mode, TaskType.QUIZ)
    if intent.plan.source_mode == SourceMode.WEB_ONLY:
        raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "QUIZ_REQUIRES_LOCAL_SOURCES",
            "Quiz generation must use local or hybrid sources, not web_only.",
        )
    chunks = store.project_chunks(user, payload.project_id)
    if chunks is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    retrieved = retrieve_local_chunks(chunks, intent.clean_message, limit=10)
    if not retrieved:
        raise_api_error(
            status.HTTP_409_CONFLICT,
            "DOCUMENT_NOT_INDEXED",
            "No ready local document chunks exist for quiz generation.",
        )

    _, citations, _ = build_grounded_answer(intent.clean_message, SourceMode(intent.plan.source_mode), retrieved)
    quiz_set = generate_quiz_set(
        SourceMode(intent.plan.source_mode),
        retrieved,
        citations,
        payload.single_choice_count,
        payload.short_answer_count,
    )
    tool_calls = [
        ToolCallTrace(
            id=uuid4(),
            tool_name="query_local_docs",
            input_summary={"project_id": str(payload.project_id), "query_length": len(intent.clean_message)},
            output_summary={"chunks": len(retrieved)},
            status="succeeded",
            latency_ms=0,
        ),
        ToolCallTrace(
            id=uuid4(),
            tool_name="generate_quiz",
            input_summary={"schema": "QuizSet", "requested_questions": payload.single_choice_count + payload.short_answer_count},
            output_summary={"questions": len(quiz_set.questions)},
            status="succeeded",
            latency_ms=0,
        ),
        ToolCallTrace(
            id=uuid4(),
            tool_name="save_quiz",
            input_summary={"project_id": str(payload.project_id)},
            output_summary={"quiz_set_id": str(quiz_set.id)},
            status="succeeded",
            latency_ms=0,
        ),
    ]
    policy_result = validate_tool_policy(intent.plan, [call.tool_name for call in tool_calls])
    validation_result = {
        "passed": policy_result["passed"] and len(quiz_set.questions) > 0,
        "source_policy": policy_result,
        "question_count": len(quiz_set.questions),
    }
    run_id, trace_id = store.record_run(
        user=user,
        project_id=payload.project_id,
        plan=intent.plan,
        router_reason=intent.router_reason,
        retrieved_chunks=retrieved,
        citations=citations,
        tool_calls=tool_calls,
        validation_result=validation_result,
    )
    store.save_quiz_set(payload.project_id, quiz_set)
    return QuizResponse(
        quiz_set=quiz_set,
        run_id=run_id,
        trace_id=trace_id,
        validation_status="passed" if validation_result["passed"] else "failed",
    )


# 查看项目 Quiz 历史。
@router.get("/projects/{project_id}/quiz", response_model=QuizHistoryResponse)
def list_quiz_history(
    project_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> QuizHistoryResponse:
    quiz_sets = store.list_quiz_sets(user, project_id)
    if quiz_sets is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    return QuizHistoryResponse(project_id=project_id, quiz_sets=quiz_sets)
