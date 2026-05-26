from uuid import uuid4

from fastapi import APIRouter, Depends, status

from researchmate_api.dependencies import get_current_user, raise_api_error
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import CurrentUser, SourceMode, TaskType
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import build_demo_web_evidence, build_grounded_answer
from researchmate_api.services.retrieval import retrieve_local_chunks
from researchmate_api.services.source_policy import resolve_intent, validate_tool_policy
from researchmate_api.services.store import store


router = APIRouter()


# 接收 Ask 请求并返回结构化、可溯源回答。
@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, user: CurrentUser = Depends(get_current_user)) -> AskResponse:
    if store.get_project(user, payload.project_id) is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")
    if not store.increment_usage(user, "ask", limit=200):
        raise_api_error(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", "Daily ask quota exceeded.")

    intent = resolve_intent(payload.message, SourceMode(payload.selected_mode), TaskType.ANSWER)
    if intent.plan.task_type == TaskType.QUIZ:
        raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "TASK_ROUTE_MISMATCH",
            "Use POST /api/v1/quiz for /quiz requests.",
        )

    chunks = store.project_chunks(user, payload.project_id)
    if chunks is None:
        raise_api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project was not found.")

    retrieved = []
    tool_calls: list[ToolCallTrace] = []
    if intent.plan.source_mode in {SourceMode.LOCAL_ONLY, SourceMode.HYBRID}:
        retrieved = retrieve_local_chunks(chunks, intent.clean_message, limit=5)
        tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="query_local_docs",
                input_summary={"project_id": str(payload.project_id), "query_length": len(intent.clean_message)},
                output_summary={"chunks": len(retrieved)},
                status="succeeded",
                latency_ms=0,
            )
        )
        if not retrieved and intent.plan.source_mode == SourceMode.LOCAL_ONLY:
            raise_api_error(
                status.HTTP_409_CONFLICT,
                "DOCUMENT_NOT_INDEXED",
                "No ready local document chunks exist for this project.",
            )

    if intent.plan.source_mode == SourceMode.WEB_ONLY:
        web_chunk = build_demo_web_evidence(intent.clean_message)
        web_chunk.user_id = user.id
        web_chunk.project_id = payload.project_id
        retrieved = [web_chunk]
        tool_calls.extend(
            [
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="search_web",
                    input_summary={"query_length": len(intent.clean_message)},
                    output_summary={"provider": "demo", "results": 1},
                    status="succeeded",
                    latency_ms=0,
                ),
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="read_url",
                    input_summary={"url": web_chunk.url},
                    output_summary={"provider": "demo", "chars": len(web_chunk.text)},
                    status="succeeded",
                    latency_ms=0,
                ),
            ]
        )
    elif intent.plan.source_mode == SourceMode.HYBRID and not retrieved:
        web_chunk = build_demo_web_evidence(intent.clean_message)
        web_chunk.user_id = user.id
        web_chunk.project_id = payload.project_id
        retrieved = [web_chunk]
        tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="search_web",
                input_summary={"query_length": len(intent.clean_message), "reason": "local_empty"},
                output_summary={"provider": "demo", "results": 1},
                status="succeeded",
                latency_ms=0,
            )
        )

    answer, citations, summary = build_grounded_answer(
        intent.clean_message,
        SourceMode(intent.plan.source_mode),
        retrieved,
    )
    tool_calls.append(
        ToolCallTrace(
            id=uuid4(),
            tool_name="generate_answer",
            input_summary={"schema": "GroundedAnswer", "citation_count": len(citations)},
            output_summary={"answer_chars": len(answer)},
            status="succeeded",
            latency_ms=0,
        )
    )
    policy_result = validate_tool_policy(intent.plan, [call.tool_name for call in tool_calls])
    validation_result = {
        "passed": policy_result["passed"] and (len(citations) > 0 or intent.plan.source_mode == SourceMode.LOCAL_ONLY),
        "source_policy": policy_result,
        "citation_count": len(citations),
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
    response = AskResponse(
        run_id=run_id,
        answer=answer,
        mode=intent.plan.source_mode,
        sources=summary,
        citations=citations,
        trace_id=trace_id,
        validation_status="passed" if validation_result["passed"] else "failed",
    )
    return store.save_ask_response(response)
