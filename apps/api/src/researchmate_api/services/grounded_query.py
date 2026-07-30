from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from researchmate_api.config import Settings
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import (
    CurrentUser,
    DocumentStatus,
    ExecutionPlan,
    SourceSummary,
    SourceType,
    TaskType,
)
from researchmate_api.schemas.conversation import ConversationMessage
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.answering import (
    ProviderOutputError,
    build_chat_answer,
    build_grounded_answer,
    build_llm_chat_answer,
    build_llm_grounded_answer,
)
from researchmate_api.services.llm import ChatProvider, ProviderRequestError
from researchmate_api.services.qdrant_store import QdrantHybridStore, VectorStoreRequestError
from researchmate_api.services.rerank import RerankCoordinator
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    bm25_candidates,
    estimate_tokens,
    fuse_candidates,
    pack_chunks,
)
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository
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
        settings: Settings,
        repository: ResearchMateRepository,
        chat_provider: ChatProvider | None,
        hybrid_store: QdrantHybridStore | None,
        reranker: RerankCoordinator,
        web_search: TavilyWebSearchProvider | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.chat_provider = chat_provider
        self.hybrid_store = hybrid_store
        self.reranker = reranker
        self.web_search = web_search

    def execute(self, user: CurrentUser, payload: AskRequest) -> AskResponse:
        request_started = monotonic()
        project = self.repository.get_project(user, payload.project_id)
        if project is None or project.status != "active":
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        if not self.repository.increment_usage(user, "ask", limit=200):
            self._error("RATE_LIMITED", "Daily ask quota exceeded.", 429)
        conversation = self.repository.ensure_conversation(
            user, payload.project_id, payload.conversation_id, payload.message
        )
        if conversation is None:
            self._error("CONVERSATION_NOT_FOUND", "Conversation was not found.", 404)
        history = self._history_context(
            user,
            conversation.id,
            self.repository.conversation_messages(user, conversation.id) or [],
        )
        if project.kind == "workspace":
            project_memory = self.repository.project_memory_context(
                user,
                payload.project_id,
                conversation.id,
            ) or []
            history = [*self._bounded_project_memory(project_memory), *history]
            documents = self.repository.list_project_documents(user, payload.project_id) or []
            chunks = self.repository.project_chunks(user, payload.project_id)
        else:
            documents = self.repository.list_conversation_documents(
                user, conversation.id
            ) or []
            chunks = self.repository.conversation_chunks(
                user, payload.project_id, conversation.id
            )
        if chunks is None:
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        if documents and not chunks and any(
            document.status
            in {
                DocumentStatus.UPLOADED,
                DocumentStatus.PARSING,
                DocumentStatus.PARSED,
                DocumentStatus.INDEXING,
            }
            for document in documents
        ):
            self._error(
                "DOCUMENT_PROCESSING",
                "Uploaded documents are still being processed.",
                409,
            )

        retrieved: list[ChunkEntry] = []
        tool_calls: list[ToolCallTrace] = []
        local_total = sum(estimate_tokens(chunk.text) for chunk in chunks)
        full_context = bool(chunks) and local_total <= self.settings.full_context_token_limit
        candidates: list[RetrievalCandidate] = []
        if chunks:
            local_started = monotonic()
            if full_context:
                candidates = [
                    RetrievalCandidate(chunk=chunk, score=1 / index, lexical_rank=index)
                    for index, chunk in enumerate(chunks, start=1)
                ]
                strategy = "full_context"
            else:
                lexical = bm25_candidates(chunks, payload.message, limit=30)
                semantic = self._semantic_candidates(
                    user,
                    payload.project_id,
                    payload.message,
                    chunks,
                    (
                        [str(document.id) for document in documents]
                        if project.kind == "personal"
                        else None
                    ),
                )
                candidates = fuse_candidates(
                    lexical,
                    semantic,
                    limit=self.settings.rerank_candidate_limit,
                )
                strategy = "hybrid_retrieval"
            tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="query_local_docs",
                    input_summary={
                        "project_id": str(payload.project_id),
                        "query_length": len(payload.message),
                    },
                    output_summary={
                        "candidates": len(candidates),
                        "full_context": full_context,
                        "estimated_tokens": local_total,
                    },
                    status="succeeded",
                    latency_ms=round((monotonic() - local_started) * 1000),
                )
            )
        else:
            strategy = "web" if payload.web_enabled else "chat"

        if payload.web_enabled:
            web_started = monotonic()
            web_chunks = self._retrieve_web(
                user, payload.project_id, payload.message, limit=5
            )
            candidates.extend(
                RetrievalCandidate(chunk=chunk, score=1 / (60 + index))
                for index, chunk in enumerate(web_chunks, start=1)
            )
            strategy = "hybrid_retrieval_web" if chunks else "web"
            tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="search_web",
                    input_summary={"query_length": len(payload.message)},
                    output_summary={"provider": "tavily", "results": len(web_chunks)},
                    status="succeeded",
                    latency_ms=round((monotonic() - web_started) * 1000),
                )
            )

        if len(candidates) > self.settings.rerank_candidate_limit:
            candidates = self._limit_rerank_candidates(
                candidates,
                self.settings.rerank_candidate_limit,
            )
        rerank_config = self.repository.get_runtime_rerank_config()
        selected_rerank_provider = (
            rerank_config.provider
            if rerank_config.version > 1
            else self.settings.rerank_provider_default
        )
        rerank_result = None
        if candidates and not (full_context and not payload.web_enabled):
            rerank_started = monotonic()
            rerank_result = self.reranker.execute(
                selected_rerank_provider,
                payload.message,
                candidates,
                user_id=str(user.id),
                project_id=str(payload.project_id),
                top_n=len(candidates) if full_context and not payload.web_enabled else None,
            )
            retrieved = pack_chunks(
                [item.chunk for item in rerank_result.candidates],
                self.settings.retrieval_evidence_token_budget,
            )
            tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="rerank_evidence",
                    input_summary={
                        "candidate_count": len(candidates),
                        "config_version": rerank_config.version,
                    },
                    output_summary={
                        "provider": rerank_result.provider,
                        "model": rerank_result.model,
                        "results": len(retrieved),
                        "degraded": rerank_result.degraded,
                        "fallback_reason": rerank_result.fallback_reason,
                    },
                    status="succeeded",
                    latency_ms=round((monotonic() - rerank_started) * 1000),
                )
            )
        elif candidates:
            # Every ready local chunk already fits. Avoid an external rerank round trip
            # without dropping or reordering evidence.
            retrieved = pack_chunks(
                [item.chunk for item in candidates],
                self.settings.full_context_token_limit,
            )
        plan = self._execution_plan(
            strategy,
            payload.web_enabled,
            bool(chunks),
            rerank_used=rerank_result is not None,
        )

        llm_result = None
        generation_started = monotonic()
        try:
            if retrieved:
                if self.chat_provider is not None:
                    answer, citations, summary, llm_result = build_llm_grounded_answer(
                        self.chat_provider,
                        payload.message,
                        retrieved,
                        history,
                        self.settings.ask_max_output_tokens,
                    )
                else:
                    answer, citations, summary = build_grounded_answer(
                        payload.message, retrieved
                    )
            else:
                if self.chat_provider is not None:
                    answer, llm_result = build_llm_chat_answer(
                        self.chat_provider,
                        payload.message,
                        history,
                        self.settings.ask_max_output_tokens,
                    )
                else:
                    answer = build_chat_answer(payload.message)
                citations = []
                summary = SourceSummary()
        except ProviderOutputError as exc:
            raise GroundedQueryError(
                "LLM_OUTPUT_INVALID",
                "The model response failed grounded-output validation.",
                502,
            ) from exc
        except ProviderRequestError as exc:
            raise GroundedQueryError(
                "LLM_UNAVAILABLE",
                "The model provider is temporarily unavailable.",
                503,
            ) from exc

        tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="generate_answer",
                input_summary={
                    "schema": "GroundedAnswer" if retrieved else "ChatAnswer",
                    "history_messages": len(history),
                    "evidence_tokens": sum(estimate_tokens(item.text) for item in retrieved),
                },
                output_summary={"answer_chars": len(answer), "citation_count": len(citations)},
                status="succeeded",
                latency_ms=round((monotonic() - generation_started) * 1000),
            )
        )
        validation_result = {
            "passed": bool(answer) and (not retrieved or bool(citations)),
            "citation_count": len(citations),
            "context_strategy": strategy,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
        }
        runtime_metadata = {
            "context_strategy": strategy,
            "web_enabled": payload.web_enabled,
            "rerank_provider": rerank_result.provider if rerank_result else None,
            "rerank_model": rerank_result.model if rerank_result else None,
            "rerank_config_version": rerank_config.version,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
            "fallback_reason": rerank_result.fallback_reason if rerank_result else None,
            "candidate_count": len(candidates),
            "retrieved_count": len(retrieved),
            "estimated_input_tokens": (
                estimate_tokens(payload.message)
                + sum(estimate_tokens(item.content) for item in history)
                + sum(estimate_tokens(item.text) for item in retrieved)
            ),
            "estimated_output_tokens": estimate_tokens(answer),
            "provider_input_tokens": (
                llm_result.prompt_tokens if llm_result is not None else None
            ),
            "provider_output_tokens": (
                llm_result.completion_tokens if llm_result is not None else None
            ),
            "total_latency_ms": round((monotonic() - request_started) * 1000),
        }
        run_id, trace_id = self.repository.record_run(
            user=user,
            project_id=payload.project_id,
            message=payload.message,
            plan=plan,
            router_reason=f"Unified chat resolved {strategy} from document readiness and web_enabled.",
            retrieved_chunks=retrieved,
            citations=citations,
            tool_calls=tool_calls,
            validation_result=validation_result,
            conversation_id=conversation.id,
            runtime_metadata=runtime_metadata,
            assistant_answer=answer,
        )
        response = AskResponse(
            run_id=run_id,
            conversation_id=conversation.id,
            answer=answer,
            sources=summary,
            citations=citations,
            trace_id=trace_id,
            validation_status="passed" if validation_result["passed"] else "failed",
            rerank_degraded=rerank_result.degraded if rerank_result else False,
            fallback_reason=rerank_result.fallback_reason if rerank_result else None,
        )
        return response

    def search(self, user: CurrentUser, project_id: UUID, query: str, limit: int = 10):
        project = self.repository.get_project(user, project_id)
        if project is None or project.status != "active":
            self._error("PROJECT_NOT_FOUND", "Project was not found.", 404)
        chunks = self.repository.project_chunks(user, project_id) or []
        return [item.chunk for item in bm25_candidates(chunks, query, limit=limit)]

    def _bounded_history(
        self, messages: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        selected: list[ConversationMessage] = []
        used = 0
        for message in reversed(messages):
            size = estimate_tokens(message.content)
            if selected and used + size > self.settings.chat_recent_token_budget:
                break
            selected.append(message)
            used += size
        return list(reversed(selected))

    @staticmethod
    def _bounded_project_memory(
        messages: list[ConversationMessage],
        token_budget: int = 1600,
    ) -> list[ConversationMessage]:
        selected: list[ConversationMessage] = []
        used = 0
        for message in reversed(messages):
            size = estimate_tokens(message.content)
            if selected and used + size > token_budget:
                break
            selected.append(message)
            used += size
        selected.reverse()
        if not selected:
            return []
        memory = "\n".join(
            f"{message.role}: {message.content}" for message in selected
        )
        return [
            ConversationMessage(
                id=uuid4(),
                conversation_id=selected[-1].conversation_id,
                role="assistant",
                content=(
                    "Project memory from other conversations follows. Treat it as "
                    "background context, not as the current dialogue.\n"
                    f"<project_memory>\n{memory}\n</project_memory>"
                ),
                citations=[],
                created_at=selected[-1].created_at,
            )
        ]

    def _history_context(
        self,
        user: CurrentUser,
        conversation_id: UUID,
        messages: list[ConversationMessage],
    ) -> list[ConversationMessage]:
        summary_state = self.repository.conversation_summary(user, conversation_id)
        summary, summarized_count = summary_state or (None, 0)
        keep_recent = 8
        compact_until = max(0, len(messages) - keep_recent)
        pending = messages[summarized_count:compact_until]
        if (
            self.chat_provider is not None
            and pending
            and sum(estimate_tokens(item.content) for item in pending)
            > self.settings.chat_summary_trigger_tokens
        ):
            try:
                summary_messages = [
                        {
                            "role": "system",
                            "content": (
                                "Compact this conversation into durable factual context. "
                                "Preserve decisions, constraints, unresolved questions, and user "
                                "preferences. Do not add facts. Return plain text only."
                            ),
                        },
                        {
                            "role": "user",
                            "content": "\n".join(
                                [
                                    f"Previous summary:\n{summary}" if summary else "",
                                    *[
                                        f"{item.role}: {item.content}"
                                        for item in pending
                                    ],
                                ]
                            ),
                        },
                    ]
                bounded = getattr(self.chat_provider, "complete_bounded", None)
                result = (
                    bounded(
                        summary_messages,
                        max_tokens=self.settings.chat_summary_token_budget,
                    )
                    if callable(bounded)
                    else self.chat_provider.complete(summary_messages)
                )
                summary = result.content.strip()
                while (
                    len(summary) > 1
                    and estimate_tokens(summary) > self.settings.chat_summary_token_budget
                ):
                    summary = summary[: int(len(summary) * 0.9)].rstrip()
                summarized_count = compact_until
                self.repository.update_conversation_summary(
                    user,
                    conversation_id,
                    summary,
                    summarized_count,
                )
            except ProviderRequestError:
                pass
        recent = self._bounded_history(messages[summarized_count:])
        if not summary:
            return recent
        return [
            ConversationMessage(
                id=uuid4(),
                conversation_id=conversation_id,
                role="assistant",
                content=f"Conversation summary:\n{summary}",
                citations=[],
                created_at=datetime.now(UTC),
            ),
            *recent,
        ]

    def _semantic_candidates(
        self,
        user: CurrentUser,
        project_id: UUID,
        query: str,
        chunks: list[ChunkEntry],
        document_ids: list[str] | None = None,
    ) -> list[ChunkEntry]:
        if self.hybrid_store is None:
            return []
        try:
            matches = self.hybrid_store.query_dense(
                user_id=str(user.id),
                project_id=str(project_id),
                source_type=SourceType.LOCAL_DOC,
                text=query,
                limit=30,
                document_ids=document_ids,
            )
        except VectorStoreRequestError:
            return []
        ids: list[UUID] = []
        for match in matches:
            try:
                ids.append(UUID(str(match["payload"]["chunk_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        return self.repository.get_chunks_by_ids(user, project_id, ids) or []

    def _retrieve_web(
        self, user: CurrentUser, project_id: UUID, query: str, *, limit: int
    ) -> list[ChunkEntry]:
        if self.web_search is None:
            self._error(
                "WEB_SEARCH_NOT_CONFIGURED",
                "Web evidence is unavailable until the search provider is configured.",
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
    def _limit_rerank_candidates(
        candidates: list[RetrievalCandidate],
        limit: int,
    ) -> list[RetrievalCandidate]:
        """Bound provider payloads while preserving Web and document diversity."""
        web = [
            candidate
            for candidate in candidates
            if candidate.chunk.source_type == SourceType.WEB_PAGE
        ]
        local = [
            candidate
            for candidate in candidates
            if candidate.chunk.source_type != SourceType.WEB_PAGE
        ]
        local_limit = max(0, limit - min(len(web), limit))
        diversified: list[RetrievalCandidate] = []
        seen_documents = set()
        for candidate in local:
            key = candidate.chunk.document_id or candidate.chunk.id
            if key in seen_documents:
                continue
            seen_documents.add(key)
            diversified.append(candidate)
            if len(diversified) >= local_limit:
                break
        selected_ids = {candidate.chunk.id for candidate in diversified}
        diversified.extend(
            candidate
            for candidate in local
            if candidate.chunk.id not in selected_ids
        )
        return [*diversified[:local_limit], *web[:limit]][:limit]

    @staticmethod
    def _execution_plan(
        strategy: str,
        web_enabled: bool,
        has_documents: bool,
        *,
        rerank_used: bool,
    ) -> ExecutionPlan:
        tools = []
        if has_documents:
            tools.append("query_local_docs")
        if web_enabled:
            tools.append("search_web")
        if rerank_used:
            tools.append("rerank_evidence")
        tools.append("generate_answer")
        return ExecutionPlan(
            task_type=TaskType.ANSWER,
            allowed_tools=tools,
            requires_local_docs=has_documents,
            requires_web=web_enabled,
            context_strategy=strategy,
            output_schema=(
                "ChatAnswer" if strategy == "chat" else "GroundedAnswer"
            ),
        )

    @staticmethod
    def _error(code: str, message: str, status_code: int):
        raise GroundedQueryError(code, message, status_code)
