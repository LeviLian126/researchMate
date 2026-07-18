from __future__ import annotations

from uuid import UUID, uuid4

from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import CurrentUser, SourceMode, SourceType, TaskType
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import (
    ProviderOutputError,
    build_grounded_answer,
    build_llm_grounded_answer,
)
from researchmate_api.services.llm import ChatProvider, ProviderRequestError
from researchmate_api.services.qdrant_store import QdrantHybridStore, VectorStoreRequestError
from researchmate_api.services.retrieval import retrieve_local_chunks
from researchmate_api.services.source_policy import resolve_intent, validate_tool_policy
from researchmate_api.services.store import ResearchMateRepository
from researchmate_api.services.web_search import TavilyWebSearchProvider, WebSearchRequestError


class GroundedQueryError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class GroundedQueryService:
    def __init__(
        self,
        *,
        repository: ResearchMateRepository,
        chat_provider: ChatProvider | None,
        hybrid_store: QdrantHybridStore | None,
        web_search: TavilyWebSearchProvider | None = None,
    ) -> None:
        self.repository = repository
        self.chat_provider = chat_provider
        self.hybrid_store = hybrid_store
        self.web_search = web_search

    def execute(self, user: CurrentUser, payload: AskRequest) -> AskResponse:
        if self.repository.get_project(user, payload.project_id) is None:
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        if not self.repository.increment_usage(user, "ask", limit=200):
            self._error("RATE_LIMITED", "Daily ask quota exceeded.", 429)
        intent = resolve_intent(payload.message, SourceMode(payload.selected_mode), TaskType.ANSWER)
        if intent.plan.task_type == TaskType.QUIZ:
            self._error("TASK_ROUTE_MISMATCH", "Use the quiz operation for /quiz requests.", 422)
        chunks = self.repository.project_chunks(user, payload.project_id)
        if chunks is None:
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        retrieved = []
        tool_calls: list[ToolCallTrace] = []
        if intent.plan.source_mode in {SourceMode.LOCAL_ONLY, SourceMode.HYBRID}:
            retrieved = self._retrieve_local(user, payload.project_id, intent.clean_message, chunks)
            tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="query_local_docs",
                    input_summary={
                        "project_id": str(payload.project_id),
                        "query_length": len(intent.clean_message),
                    },
                    output_summary={
                        "chunks": len(retrieved),
                        "retriever": (
                            "qdrant_hybrid_rrf" if self.hybrid_store else "token_overlap"
                        ),
                    },
                    status="succeeded",
                    latency_ms=0,
                )
            )
            if not retrieved and intent.plan.source_mode == SourceMode.LOCAL_ONLY:
                self._error(
                    "EVIDENCE_NOT_FOUND" if chunks else "DOCUMENT_NOT_INDEXED",
                    (
                        "No local evidence matched this question."
                        if chunks
                        else "No ready local document chunks exist for this project."
                    ),
                    409,
                )
        if intent.plan.source_mode in {SourceMode.WEB_ONLY, SourceMode.HYBRID}:
            web_evidence = self._retrieve_web(
                user, payload.project_id, intent.clean_message, limit=5
            )
            if intent.plan.source_mode == SourceMode.WEB_ONLY:
                retrieved = web_evidence
            else:
                retrieved.extend(web_evidence)
            tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="search_web",
                    input_summary={"query_length": len(intent.clean_message), "reason": "local_empty"},
                    output_summary={"provider": "tavily", "results": len(web_evidence)},
                    status="succeeded",
                    latency_ms=0,
                )
            )
        try:
            answer, citations, summary = (
                build_llm_grounded_answer(
                    self.chat_provider,
                    intent.clean_message,
                    SourceMode(intent.plan.source_mode),
                    retrieved,
                )
                if self.chat_provider is not None
                else build_grounded_answer(
                    intent.clean_message,
                    SourceMode(intent.plan.source_mode),
                    retrieved,
                )
            )
        except ProviderOutputError as exc:
            raise GroundedQueryError(
                "LLM_OUTPUT_INVALID", "The model response failed grounded-output validation.", 502
            ) from exc
        except ProviderRequestError as exc:
            raise GroundedQueryError(
                "LLM_UNAVAILABLE",
                (
                    "The model provider is temporarily unavailable. Retry later."
                    if exc.retryable
                    else "The model provider rejected the request."
                ),
                503,
            ) from exc
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
            "passed": policy_result["passed"]
            and (len(citations) > 0 or intent.plan.source_mode == SourceMode.LOCAL_ONLY),
            "source_policy": policy_result,
            "citation_count": len(citations),
        }
        run_id, trace_id = self.repository.record_run(
            user=user,
            project_id=payload.project_id,
            message=intent.clean_message,
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
        return self.repository.save_ask_response(user, response)

    def search(self, user: CurrentUser, project_id: UUID, query: str, limit: int = 10):
        if self.repository.get_project(user, project_id) is None:
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        chunks = self.repository.project_chunks(user, project_id) or []
        return self._retrieve_local(user, project_id, query, chunks, limit=limit)

    def _retrieve_local(
        self,
        user: CurrentUser,
        project_id: UUID,
        query: str,
        chunks,
        *,
        limit: int = 5,
    ):
        if self.hybrid_store is None:
            return retrieve_local_chunks(chunks, query, limit=limit)
        try:
            matches = self.hybrid_store.query(
                user_id=str(user.id),
                project_id=str(project_id),
                source_type=SourceType.LOCAL_DOC,
                text=query,
                limit=limit,
            )
        except VectorStoreRequestError as exc:
            raise GroundedQueryError(
                "RETRIEVAL_UNAVAILABLE", "Hybrid retrieval is temporarily unavailable.", 503
            ) from exc
        ids = []
        for match in matches:
            try:
                ids.append(UUID(str(match["payload"]["chunk_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        return self.repository.get_chunks_by_ids(user, project_id, ids) or []

    def _retrieve_web(
        self, user: CurrentUser, project_id: UUID, query: str, *, limit: int
    ):
        if self.web_search is None:
            self._error(
                "WEB_SEARCH_NOT_CONFIGURED",
                "Web evidence is unavailable until the backend search provider is configured.",
                503,
            )
        try:
            results = self.web_search.search(
                user_id=user.id,
                project_id=project_id,
                query=query,
                limit=limit,
            )
        except WebSearchRequestError as exc:
            raise GroundedQueryError(
                "WEB_SEARCH_UNAVAILABLE",
                "The web search provider is temporarily unavailable.",
                503,
            ) from exc
        if not results:
            self._error("WEB_EVIDENCE_NOT_FOUND", "No usable web evidence was found.", 409)
        return results

    @staticmethod
    def _error(code: str, message: str, status_code: int):
        raise GroundedQueryError(code, message, status_code)
