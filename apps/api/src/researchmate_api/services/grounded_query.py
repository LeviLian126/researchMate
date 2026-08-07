"""Orchestrate one Ask request across scope, retrieval, generation, and persistence."""

from __future__ import annotations

from time import monotonic
from uuid import uuid4

from researchmate_api.config import Settings
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.query_context import ConversationContextBuilder
from researchmate_api.services.query_conversation import QueryConversationCoordinator
from researchmate_api.services.query_errors import GroundedQueryError, raise_grounded_error
from researchmate_api.services.query_execution import (
    WebEvidenceError,
    build_execution_plan,
    limit_rerank_candidates,
    retrieve_web,
)
from researchmate_api.services.query_generation import AnswerGenerationError, generate_answer
from researchmate_api.services.query_retrieval import LocalEvidenceRetriever, RetrievalOutcome
from researchmate_api.services.rerank import RerankCoordinator
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    estimate_tokens,
    pack_chunks,
)
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository
from researchmate_api.services.web_search import TavilyWebSearchProvider


class GroundedQueryService:
    """Coordinate the unified Ask use case without owning adapter mechanics."""

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
        """Bind the application dependencies required for one Ask execution."""
        self.settings = settings
        self.repository = repository
        self.chat_provider = chat_provider
        self.hybrid_store = hybrid_store
        self.reranker = reranker
        self.web_search = web_search
        self.local_retriever = LocalEvidenceRetriever(settings, repository, hybrid_store)
        self.context_builder = ConversationContextBuilder(
            repository,
            chat_provider,
            recent_token_budget=settings.chat_recent_token_budget,
            summary_trigger_tokens=settings.chat_summary_trigger_tokens,
            summary_token_budget=settings.chat_summary_token_budget,
        )
        self.conversations = QueryConversationCoordinator(repository, self.context_builder)

    def execute(self, user: CurrentUser, payload: AskRequest) -> AskResponse:
        """Execute a validated Ask request and persist its trace and dialogue result."""
        request_started = monotonic()
        preparation = self.conversations.prepare(user, payload)
        project = preparation.project
        conversation = preparation.conversation
        documents = preparation.documents
        chunks = preparation.chunks
        context_outcome = preparation.context
        history = context_outcome.messages

        retrieved: list[ChunkEntry] = []
        tool_calls: list[ToolCallTrace] = []
        local_total = 0
        full_context = False
        retrieval_outcome = RetrievalOutcome([], "hybrid_retrieval", False, 0)
        candidates: list[RetrievalCandidate] = []
        if chunks:
            local_started = monotonic()
            retrieval_outcome = self.local_retriever.retrieve(
                user,
                payload.project_id,
                payload.message,
                chunks,
                document_ids=(
                    [str(document.id) for document in documents]
                    if project.kind == "personal"
                    else None
                ),
            )
            candidates = retrieval_outcome.candidates
            strategy = retrieval_outcome.strategy
            full_context = retrieval_outcome.full_context
            local_total = retrieval_outcome.estimated_tokens
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
                        "degraded": retrieval_outcome.degraded,
                        "fallback_reason": retrieval_outcome.reason,
                    },
                    status="succeeded",
                    latency_ms=round((monotonic() - local_started) * 1000),
                )
            )
        else:
            strategy = "web" if payload.web_enabled else "chat"

        if payload.web_enabled:
            web_started = monotonic()
            try:
                web_chunks = retrieve_web(
                    self.web_search, user, payload.project_id, payload.message, limit=5
                )
            except WebEvidenceError as exc:
                raise GroundedQueryError(exc.code, exc.message, exc.status_code) from exc
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
            candidates = limit_rerank_candidates(
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
                top_n=None,
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
            # Every relevant local candidate already fits; packing remains a size policy.
            retrieved = pack_chunks(
                [item.chunk for item in candidates],
                self.settings.full_context_token_limit,
            )
        plan = build_execution_plan(
            strategy,
            payload.web_enabled,
            bool(chunks),
            rerank_used=rerank_result is not None,
        )

        try:
            generation = generate_answer(
                self.chat_provider,
                payload.message,
                retrieved,
                history,
                documents_present=bool(chunks),
                web_enabled=payload.web_enabled,
                max_output_tokens=self.settings.ask_max_output_tokens,
            )
        except AnswerGenerationError as exc:
            raise GroundedQueryError(exc.code, exc.message, exc.status_code) from exc
        # Quota counts successful generation only; provider failures do not consume quota.
        if not self.repository.increment_usage(user, "ask", limit=200):
            raise_grounded_error("RATE_LIMITED", "Daily ask quota exceeded.", 429)
        answer = generation.answer
        citations = generation.citations
        summary = generation.summary
        llm_result = generation.provider_result
        conversation = self.conversations.ensure_for_commit(user, payload, conversation)

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
                latency_ms=generation.latency_ms,
            )
        )
        validation_result = {
            "passed": bool(answer) and (not retrieved or bool(citations)),
            "citation_count": len(citations),
            "context_strategy": strategy,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
            "retrieval_degraded": retrieval_outcome.degraded,
            "summary_degraded": context_outcome.degraded,
        }
        runtime_metadata = {
            "context_strategy": strategy,
            "web_enabled": payload.web_enabled,
            "rerank_provider": rerank_result.provider if rerank_result else None,
            "rerank_model": rerank_result.model if rerank_result else None,
            "rerank_config_version": rerank_config.version,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
            "fallback_reason": (
                rerank_result.fallback_reason
                if rerank_result and rerank_result.fallback_reason
                else retrieval_outcome.reason or context_outcome.reason
            ),
            "candidate_count": len(candidates),
            "retrieved_count": len(retrieved),
            "estimated_input_tokens": (
                estimate_tokens(payload.message)
                + sum(estimate_tokens(item.content) for item in history)
                + sum(estimate_tokens(item.text) for item in retrieved)
            ),
            "estimated_output_tokens": estimate_tokens(answer),
            "provider_input_tokens": (llm_result.prompt_tokens if llm_result is not None else None),
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
        return AskResponse(
            run_id=run_id,
            conversation_id=conversation.id,
            answer=answer,
            sources=summary,
            citations=citations,
            trace_id=trace_id,
            validation_status="passed" if validation_result["passed"] else "failed",
            rerank_degraded=rerank_result.degraded if rerank_result else False,
            retrieval_degraded=retrieval_outcome.degraded,
            summary_degraded=context_outcome.degraded,
            fallback_reason=(
                rerank_result.fallback_reason
                if rerank_result and rerank_result.fallback_reason
                else retrieval_outcome.reason or context_outcome.reason
            ),
        )
