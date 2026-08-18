"""Orchestrate one Ask request across scope, retrieval, generation, and persistence."""

from __future__ import annotations

import logging
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

from researchmate_api.config import Settings
from researchmate_api.graph import ResearchGraph
from researchmate_api.schemas.ask import AskRequest, AskResponse
from researchmate_api.schemas.common import (
    Citation,
    ContextStrategy,
    CurrentUser,
    ExecutionPlan,
    SourceSummary,
)
from researchmate_api.schemas.conversation import (
    ConversationMessage,
    RuntimeRerankConfig,
)
from researchmate_api.schemas.document import DocumentRecord
from researchmate_api.schemas.project import ProjectRecord
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.adaptive_query_planning import AdaptiveQueryPlanner
from researchmate_api.services.evidence_sufficiency import EvidenceSufficiencyService
from researchmate_api.services.llm import ChatProvider, LLMResult
from researchmate_api.services.qdrant_store import QdrantHybridStore
from researchmate_api.services.query_context import ContextOutcome, ConversationContextBuilder
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
from researchmate_api.services.rerank import RerankCoordinator, RerankResult
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    estimate_tokens,
    pack_chunks,
)
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository
from researchmate_api.services.web_search import TavilyWebSearchProvider

LOGGER = logging.getLogger(__name__)


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
        self.local_retriever = LocalEvidenceRetriever(
            settings, repository, hybrid_store, chat_provider
        )
        self.research_graph = ResearchGraph(
            settings,
            repository,
            self.local_retriever,
            reranker,
            web_search,
            EvidenceSufficiencyService(chat_provider),
            AdaptiveQueryPlanner(settings, chat_provider),
        )
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

        if self.settings.langgraph_research_enabled:
            graph_result = self.research_graph.run(
                user,
                project,
                payload.project_id,
                payload.message,
                chunks,
                history,
                web_allowed=payload.web_enabled,
            )
            tool_calls = graph_result.tool_calls
            retrieval_outcome = graph_result.retrieval_outcome
            candidates = graph_result.candidates
            strategy = cast(ContextStrategy, graph_result.strategy)
            retrieved = graph_result.retrieved
            rerank_result = graph_result.rerank_result
            rerank_config = graph_result.rerank_config
            web_degraded = graph_result.web_degraded
            web_fallback_reason = graph_result.web_fallback_reason
            graph_runtime_metadata = graph_result.runtime_metadata
        else:
            tool_calls = []
            retrieval_outcome = RetrievalOutcome([], "hybrid_retrieval", False, 0)
            candidates: list[RetrievalCandidate] = []
            if chunks:
                retrieval_outcome, candidates, tool_call = self._retrieve_local(
                    user, payload, project, documents, chunks, history
                )
                tool_calls.append(tool_call)
                strategy: ContextStrategy = retrieval_outcome.strategy
                full_context = retrieval_outcome.full_context
            else:
                strategy = "web" if payload.web_enabled else "chat"
                full_context = retrieval_outcome.full_context

            web_degraded = False
            web_fallback_reason: str | None = None
            if payload.web_enabled:
                (
                    candidates,
                    web_degraded,
                    web_fallback_reason,
                    strategy,
                    web_tool_call,
                ) = self._retrieve_web_degraded(user, payload, bool(chunks), candidates, strategy)
                tool_calls.append(web_tool_call)

            retrieved, rerank_result, rerank_config, rerank_tool_call = self._route_and_rerank(
                user, payload, candidates, full_context, chunks
            )
            if rerank_tool_call is not None:
                tool_calls.append(rerank_tool_call)
            graph_runtime_metadata = {"research_graph_enabled": False}

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
            self._build_generation_tool_call(
                answer, citations, retrieved, history, generation.latency_ms
            )
        )
        validation_result = self._build_validation_result(
            answer,
            retrieved,
            citations,
            strategy,
            rerank_result,
            retrieval_outcome,
            web_degraded,
            context_outcome,
        )
        runtime_metadata = self._build_runtime_metadata(
            payload,
            strategy,
            rerank_result,
            rerank_config,
            retrieval_outcome,
            web_degraded,
            web_fallback_reason,
            context_outcome,
            candidates,
            retrieved,
            history,
            answer,
            llm_result,
            request_started,
        )
        runtime_metadata.update(graph_runtime_metadata)
        router_reason = (
            f"Retrieval route {retrieval_outcome.route.value}: {retrieval_outcome.route_reason}."
        )
        run_id, trace_id = self._persist_run(
            user,
            payload,
            plan,
            router_reason,
            retrieved,
            citations,
            tool_calls,
            validation_result,
            runtime_metadata,
            answer,
            conversation.id,
        )
        return self._build_response(
            run_id,
            trace_id,
            conversation.id,
            answer,
            summary,
            citations,
            validation_result,
            rerank_result,
            retrieval_outcome,
            web_degraded,
            web_fallback_reason,
            context_outcome,
        )

    def _retrieve_local(
        self,
        user: CurrentUser,
        payload: AskRequest,
        project: ProjectRecord,
        documents: list[DocumentRecord],
        chunks: list[ChunkEntry],
        history: list[ConversationMessage],
    ) -> tuple[RetrievalOutcome, list[RetrievalCandidate], ToolCallTrace]:
        """Run owner-scoped local retrieval and emit the local-docs tool trace."""
        local_started = monotonic()
        retrieval_outcome = self.local_retriever.retrieve(
            user,
            payload.project_id,
            payload.message,
            chunks,
            document_ids=(
                [str(document.id) for document in documents] if project.kind == "personal" else None
            ),
            history=history,
        )
        candidates = retrieval_outcome.candidates
        tool_call = ToolCallTrace(
            id=uuid4(),
            tool_name="query_local_docs",
            input_summary={
                "project_id": str(payload.project_id),
                "query_length": len(payload.message),
            },
            output_summary={
                "candidates": len(candidates),
                "full_context": retrieval_outcome.full_context,
                "estimated_tokens": retrieval_outcome.estimated_tokens,
                "degraded": retrieval_outcome.degraded,
                "fallback_reason": retrieval_outcome.reason,
                **retrieval_outcome.metadata(),
            },
            status="succeeded",
            latency_ms=round((monotonic() - local_started) * 1000),
        )
        return retrieval_outcome, candidates, tool_call

    def _retrieve_web_degraded(
        self,
        user: CurrentUser,
        payload: AskRequest,
        has_local_chunks: bool,
        candidates: list[RetrievalCandidate],
        strategy: ContextStrategy,
    ) -> tuple[
        list[RetrievalCandidate],
        bool,
        str | None,
        ContextStrategy,
        ToolCallTrace,
    ]:
        """Augment candidates with web evidence, degrading safely when the provider fails."""
        web_started = monotonic()
        web_degraded = False
        web_fallback_reason: str | None = None
        try:
            web_chunks = retrieve_web(
                self.web_search, user, payload.project_id, payload.message, limit=5
            )
        except WebEvidenceError as exc:
            # Web retrieval is an augmentation, not a hard dependency: when the
            # provider is unavailable (or unconfigured) we log the boundary
            # failure, empty the web evidence set, and keep flowing through
            # the local-retrieval pipeline rather than aborting the request.
            LOGGER.warning("web_evidence_degraded code=%s message=%s", exc.code, exc.message)
            web_chunks = []
            web_degraded = True
            web_fallback_reason = exc.message
        candidates.extend(
            RetrievalCandidate(chunk=chunk, score=1 / (60 + index))
            for index, chunk in enumerate(web_chunks, start=1)
        )
        if web_chunks:
            strategy = "hybrid_retrieval_web" if has_local_chunks else "web"
        elif not has_local_chunks:
            # Web evidence degraded and no local chunks were retrieved:
            # fall back to plain chat instead of leaving strategy="web".
            strategy = "chat"
        tool_call = ToolCallTrace(
            id=uuid4(),
            tool_name="search_web",
            input_summary={"query_length": len(payload.message)},
            output_summary={
                "provider": "tavily",
                "results": len(web_chunks),
                "degraded": web_degraded,
                "fallback_reason": web_fallback_reason,
            },
            status="degraded" if web_degraded else "succeeded",
            latency_ms=round((monotonic() - web_started) * 1000),
        )
        return candidates, web_degraded, web_fallback_reason, strategy, tool_call

    def _route_and_rerank(
        self,
        user: CurrentUser,
        payload: AskRequest,
        candidates: list[RetrievalCandidate],
        full_context: bool,
        chunks: list[ChunkEntry],
    ) -> tuple[
        list[ChunkEntry],
        RerankResult | None,
        RuntimeRerankConfig,
        ToolCallTrace | None,
    ]:
        """Bound rerank candidates, split lightweight vs RAG, rerank, and pack evidence."""
        if len(candidates) > self.settings.rerank_candidate_limit:
            candidates = limit_rerank_candidates(
                candidates,
                self.settings.rerank_candidate_limit,
            )

        # Separate lightweight and RAG candidates before rerank to apply budget caps early
        lightweight_candidates = [c for c in candidates if not c.chunk.has_vector]
        rag_candidates = [c for c in candidates if c.chunk.has_vector]

        # Apply budget cap to lightweight candidates before rerank
        if lightweight_candidates:
            lightweight_budget = self.settings.retrieval_evidence_token_budget // 2
            lightweight_candidates = pack_chunks(
                [c.chunk for c in lightweight_candidates], lightweight_budget
            )
            lightweight_candidates = [
                RetrievalCandidate(chunk=chunk, score=0.0) for chunk in lightweight_candidates
            ]

        rerank_config = self.repository.get_runtime_rerank_config()
        selected_rerank_provider = (
            rerank_config.provider
            if rerank_config.version > 1
            else self.settings.rerank_provider_default
        )
        retrieved: list[ChunkEntry] = []
        rerank_result: RerankResult | None = None
        tool_call: ToolCallTrace | None = None
        if rag_candidates and not (full_context and not payload.web_enabled):
            rerank_started = monotonic()
            rerank_result = self.reranker.execute(
                selected_rerank_provider,
                payload.message,
                rag_candidates,
                user_id=str(user.id),
                project_id=str(payload.project_id),
                top_n=None,
            )
            reranked_chunks = [item.chunk for item in rerank_result.candidates]
            if lightweight_candidates:
                rag_budget = self.settings.retrieval_evidence_token_budget - (
                    self.settings.retrieval_evidence_token_budget // 2
                )
                retrieved = pack_chunks(reranked_chunks, rag_budget) + [
                    c.chunk for c in lightweight_candidates
                ]
            else:
                retrieved = pack_chunks(
                    reranked_chunks,
                    self.settings.retrieval_evidence_token_budget,
                )
            tool_call = ToolCallTrace(
                id=uuid4(),
                tool_name="rerank_evidence",
                input_summary={
                    "candidate_count": len(rag_candidates),
                    "lightweight_count": len(lightweight_candidates),
                    "config_version": rerank_config.version,
                },
                output_summary={
                    "provider": rerank_result.provider,
                    "model": rerank_result.model,
                    "results": len(retrieved),
                    "lightweight_results": len(lightweight_candidates),
                    "degraded": rerank_result.degraded,
                    "fallback_reason": rerank_result.fallback_reason,
                },
                status="succeeded",
                latency_ms=round((monotonic() - rerank_started) * 1000),
            )
        elif rag_candidates:
            # Every relevant local candidate already fits; packing remains a size policy.
            retrieved = pack_chunks(
                [item.chunk for item in candidates],
                self.settings.full_context_token_limit,
            )
        elif lightweight_candidates:
            # No RAG candidates; use budget-capped lightweight chunks directly.
            retrieved = [c.chunk for c in lightweight_candidates]
        return retrieved, rerank_result, rerank_config, tool_call

    def _build_generation_tool_call(
        self,
        answer: str,
        citations: list[Citation],
        retrieved: list[ChunkEntry],
        history: list[ConversationMessage],
        latency_ms: int,
    ) -> ToolCallTrace:
        """Build the generate_answer trace entry from the generation outcome."""
        return ToolCallTrace(
            id=uuid4(),
            tool_name="generate_answer",
            input_summary={
                "schema": "GroundedAnswer" if retrieved else "ChatAnswer",
                "history_messages": len(history),
                "evidence_tokens": sum(estimate_tokens(item.text) for item in retrieved),
            },
            output_summary={"answer_chars": len(answer), "citation_count": len(citations)},
            status="succeeded",
            latency_ms=latency_ms,
        )

    def _build_validation_result(
        self,
        answer: str,
        retrieved: list[ChunkEntry],
        citations: list[Citation],
        strategy: ContextStrategy,
        rerank_result: RerankResult | None,
        retrieval_outcome: RetrievalOutcome,
        web_degraded: bool,
        context_outcome: ContextOutcome,
    ) -> dict[str, object]:
        """Assemble the public validation verdict surfaced in the trace."""
        return {
            "passed": bool(answer) and (not retrieved or bool(citations)),
            "citation_count": len(citations),
            "context_strategy": strategy,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
            "retrieval_degraded": retrieval_outcome.degraded,
            "web_degraded": web_degraded,
            "summary_degraded": context_outcome.degraded,
        }

    def _build_runtime_metadata(
        self,
        payload: AskRequest,
        strategy: ContextStrategy,
        rerank_result: RerankResult | None,
        rerank_config: RuntimeRerankConfig,
        retrieval_outcome: RetrievalOutcome,
        web_degraded: bool,
        web_fallback_reason: str | None,
        context_outcome: ContextOutcome,
        candidates: list[RetrievalCandidate],
        retrieved: list[ChunkEntry],
        history: list[ConversationMessage],
        answer: str,
        llm_result: LLMResult | None,
        request_started: float,
    ) -> dict[str, object]:
        """Assemble the developer-facing runtime metadata persisted with the run."""
        return {
            "context_strategy": strategy,
            "web_enabled": payload.web_enabled,
            "rerank_provider": rerank_result.provider if rerank_result else None,
            "rerank_model": rerank_result.model if rerank_result else None,
            "rerank_config_version": rerank_config.version,
            "rerank_degraded": rerank_result.degraded if rerank_result else False,
            "web_degraded": web_degraded,
            "fallback_reason": (
                rerank_result.fallback_reason
                if rerank_result and rerank_result.fallback_reason
                else (
                    web_fallback_reason
                    if web_degraded
                    else retrieval_outcome.reason or context_outcome.reason
                )
            ),
            "candidate_count": len(candidates),
            "retrieved_count": len(retrieved),
            **retrieval_outcome.metadata(prefix="retrieval_"),
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

    def _persist_run(
        self,
        user: CurrentUser,
        payload: AskRequest,
        plan: ExecutionPlan,
        router_reason: str,
        retrieved: list[ChunkEntry],
        citations: list[Citation],
        tool_calls: list[ToolCallTrace],
        validation_result: dict[str, object],
        runtime_metadata: dict[str, object],
        answer: str,
        conversation_id: UUID,
    ) -> tuple[UUID, UUID]:
        """Persist the run record and return the public run and trace identifiers."""
        return self.repository.record_run(
            user=user,
            project_id=payload.project_id,
            message=payload.message,
            plan=plan,
            router_reason=router_reason,
            retrieved_chunks=retrieved,
            citations=citations,
            tool_calls=tool_calls,
            validation_result=validation_result,
            conversation_id=conversation_id,
            runtime_metadata=runtime_metadata,
            assistant_answer=answer,
        )

    def _build_response(
        self,
        run_id: UUID,
        trace_id: UUID,
        conversation_id: UUID,
        answer: str,
        summary: SourceSummary,
        citations: list[Citation],
        validation_result: dict[str, object],
        rerank_result: RerankResult | None,
        retrieval_outcome: RetrievalOutcome,
        web_degraded: bool,
        web_fallback_reason: str | None,
        context_outcome: ContextOutcome,
    ) -> AskResponse:
        """Assemble the AskResponse envelope from the persisted run and generation outcome."""
        return AskResponse(
            run_id=run_id,
            conversation_id=conversation_id,
            answer=answer,
            sources=summary,
            citations=citations,
            trace_id=trace_id,
            validation_status="passed" if validation_result["passed"] else "failed",
            rerank_degraded=rerank_result.degraded if rerank_result else False,
            retrieval_degraded=retrieval_outcome.degraded,
            web_degraded=web_degraded,
            summary_degraded=context_outcome.degraded,
            fallback_reason=(
                rerank_result.fallback_reason
                if rerank_result and rerank_result.fallback_reason
                else (
                    web_fallback_reason
                    if web_degraded
                    else retrieval_outcome.reason or context_outcome.reason
                )
            ),
        )
