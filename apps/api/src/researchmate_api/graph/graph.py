"""Orchestrate bounded evidence retrieval through an explicit LangGraph workflow."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from researchmate_api.config import Settings
from researchmate_api.graph.routing import after_evidence, after_prepare, after_wiki
from researchmate_api.graph.state import ResearchState
from researchmate_api.schemas.common import CurrentUser
from researchmate_api.schemas.conversation import ConversationMessage, RuntimeRerankConfig
from researchmate_api.schemas.project import ProjectRecord
from researchmate_api.schemas.trace import ToolCallTrace
from researchmate_api.services.adaptive_query_planning import (
    AdaptiveQueryPlanner,
    AdaptiveSearchPlan,
)
from researchmate_api.services.evidence_sufficiency import (
    EvidenceAssessment,
    EvidenceSufficiencyService,
    MissingFacet,
)
from researchmate_api.services.query_execution import (
    WebEvidenceError,
    limit_rerank_candidates,
    retrieve_web,
)
from researchmate_api.services.query_planning import RetrievalPlan, plan_retrieval
from researchmate_api.services.query_retrieval import LocalEvidenceRetriever, RetrievalOutcome
from researchmate_api.services.rerank import RerankCoordinator, RerankResult
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    bm25_candidates,
    estimate_tokens,
    pack_chunks,
)
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository
from researchmate_api.services.web_search import TavilyWebSearchProvider


@dataclass(frozen=True)
class ResearchGraphResult:
    """Return graph-owned retrieval results to the Ask application boundary."""

    retrieved: list[ChunkEntry]
    candidates: list[RetrievalCandidate]
    retrieval_outcome: RetrievalOutcome
    rerank_result: RerankResult | None
    rerank_config: RuntimeRerankConfig
    strategy: str
    web_degraded: bool
    web_fallback_reason: str | None
    tool_calls: list[ToolCallTrace]
    runtime_metadata: dict[str, object]


class ResearchGraph:
    """Build one request-scoped LangGraph that cannot exceed its retrieval budget."""

    def __init__(
        self,
        settings: Settings,
        repository: ResearchMateRepository,
        local_retriever: LocalEvidenceRetriever,
        reranker: RerankCoordinator,
        web_search: TavilyWebSearchProvider | None,
        judge: EvidenceSufficiencyService,
        planner: AdaptiveQueryPlanner,
    ) -> None:
        """Bind existing retrieval capabilities without wrapping them as LangChain tools."""
        self.settings = settings
        self.repository = repository
        self.local_retriever = local_retriever
        self.reranker = reranker
        self.web_search = web_search
        self.judge = judge
        self.planner = planner

    def run(
        self,
        user: CurrentUser,
        project: ProjectRecord,
        project_id: UUID,
        question: str,
        chunks: list[ChunkEntry],
        history: list[ConversationMessage],
        *,
        web_allowed: bool,
    ) -> ResearchGraphResult:
        """Invoke one bounded graph and expose only redacted operational facts."""
        runtime = _GraphRuntime(
            graph=self,
            user=user,
            project=project,
            project_id=project_id,
            question=question,
            chunks=chunks,
            history=history,
            web_allowed=web_allowed,
        )
        final = runtime.build().invoke(runtime.initial_state())
        return runtime.result(cast(ResearchState, final))


class _GraphRuntime:
    """Own request-local node closures so concurrent asks never share graph state."""

    def __init__(
        self,
        *,
        graph: ResearchGraph,
        user: CurrentUser,
        project: ProjectRecord,
        project_id: UUID,
        question: str,
        chunks: list[ChunkEntry],
        history: list[ConversationMessage],
        web_allowed: bool,
    ) -> None:
        self.graph = graph
        self.user = user
        self.project = project
        self.project_id = project_id
        self.question = question
        self.chunks = chunks
        self.history = history
        self.web_allowed = web_allowed
        self.tool_calls: list[ToolCallTrace] = []
        self.local_outcome = RetrievalOutcome([], "hybrid_retrieval", False, 0)
        self.rerank_result: RerankResult | None = None
        self.rerank_config = graph.repository.get_runtime_rerank_config()
        self.web_degraded = False
        self.web_fallback_reason: str | None = None
        self.plan: AdaptiveSearchPlan | None = None
        self.candidates: list[RetrievalCandidate] = []
        self.seen_candidate_ids: set[UUID] = set()

    def initial_state(self) -> ResearchState:
        """Create serializable graph control state from validated application inputs."""
        has_wiki = any(
            isinstance(chunk.metadata, dict) and chunk.metadata.get("wiki_mode")
            for chunk in self.chunks
        )
        return {
            "question": self.question,
            "corpus_tokens": 0,
            "full_context_limit": self.graph.settings.full_context_token_limit,
            "wiki_threshold": self.graph.settings.wiki_sufficiency_threshold,
            "has_wiki": has_wiki,
            "web_allowed": self.web_allowed,
            "wiki_fresh": self._wiki_is_fresh() if has_wiki else False,
            "needs_raw_evidence": False,
            "local_candidates": [],
            "web_candidates": [],
            "merged_candidates": [],
            "reranked_evidence": [],
            "final_evidence": [],
            "retrieval_round": 0,
            "max_retrieval_rounds": self.graph.settings.max_retrieval_rounds,
            "evidence_sufficient": False,
            "judge_confidence": 0,
            "missing_facets": [],
            "refined_queries": [],
            "judge_degraded": False,
            "new_evidence_found": True,
            "source_strategy": "chat",
            "degraded": False,
            "fallback_reasons": [],
        }

    def build(self):
        """Compile the fixed node set and conditional edges for this request only."""
        workflow = StateGraph(ResearchState)
        workflow.add_node("prepare_context", self.prepare_context)
        workflow.add_node("use_full_context", self.use_full_context)
        workflow.add_node("select_wiki", self.select_wiki)
        workflow.add_node("judge_wiki", self.judge_wiki)
        workflow.add_node("plan_evidence", self.plan_evidence)
        workflow.add_node("search_sources", self.search_sources)
        workflow.add_node("merge_evidence", self.merge_evidence)
        workflow.add_node("rerank_evidence", self.rerank_evidence)
        workflow.add_node("judge_evidence", self.judge_evidence)
        workflow.add_node("refine_query", self.refine_query)
        workflow.add_node("generate", self.generate)
        workflow.add_edge(START, "prepare_context")
        workflow.add_conditional_edges(
            "prepare_context",
            after_prepare,
            {
                "chat": "generate",
                "full_context": "use_full_context",
                "select_wiki": "select_wiki",
                "plan": "plan_evidence",
            },
        )
        workflow.add_edge("use_full_context", "generate")
        workflow.add_edge("select_wiki", "judge_wiki")
        workflow.add_conditional_edges(
            "judge_wiki", after_wiki, {"generate": "generate", "plan": "plan_evidence"}
        )
        workflow.add_edge("plan_evidence", "search_sources")
        workflow.add_edge("search_sources", "merge_evidence")
        workflow.add_edge("merge_evidence", "rerank_evidence")
        workflow.add_edge("rerank_evidence", "judge_evidence")
        workflow.add_conditional_edges(
            "judge_evidence", after_evidence, {"generate": "generate", "refine": "refine_query"}
        )
        workflow.add_edge("refine_query", "plan_evidence")
        workflow.add_edge("generate", END)
        return workflow.compile()

    def prepare_context(self, state: ResearchState) -> ResearchState:
        """Measure the authorized corpus; project and conversation scope were validated upstream."""
        return {"corpus_tokens": sum(estimate_tokens(chunk.text) for chunk in self.chunks)}

    def use_full_context(self, state: ResearchState) -> ResearchState:
        """Preserve the cheap full-context route for corpora that fit the configured budget."""
        started = monotonic()
        self.local_outcome = self.graph.local_retriever.retrieve(
            self.user,
            self.project_id,
            self.question,
            self.chunks,
            document_ids=[str(document_id) for document_id in self._document_ids()] or None,
            history=self.history,
        )
        self.candidates = self.local_outcome.candidates
        evidence = [candidate.chunk for candidate in self.candidates]
        self.tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="query_local_docs",
                input_summary={"query_length": len(self.question)},
                output_summary={
                    "candidates": len(self.candidates),
                    **self.local_outcome.metadata(),
                },
                status="succeeded",
                latency_ms=round((monotonic() - started) * 1000),
            )
        )
        return {"final_evidence": evidence, "source_strategy": "full_context"}

    def select_wiki(self, state: ResearchState) -> ResearchState:
        """Select a small lexical Wiki candidate set instead of passing every Wiki page to a judge."""
        wiki = [
            chunk
            for chunk in self.chunks
            if isinstance(chunk.metadata, dict) and chunk.metadata.get("wiki_mode")
        ]
        selected = [
            item.chunk
            for item in bm25_candidates(
                wiki, self.question, limit=self.graph.settings.wiki_gate_candidate_limit
            )
        ]
        return {"wiki_candidates": selected, "source_strategy": "wiki"}

    def judge_wiki(self, state: ResearchState) -> ResearchState:
        """Apply deterministic exactness policy before accepting an optional model judgement."""
        evidence = state.get("wiki_candidates", [])
        assessment = self.graph.judge.assess(
            self.question,
            evidence if self.graph.settings.wiki_sufficiency_enabled else [],
        )
        return self._assessment_update(assessment)

    def plan_evidence(self, state: ResearchState) -> ResearchState:
        """Use the legacy planner as prior, then constrain an optional adaptive recommendation."""
        prior = plan_retrieval(
            self.question,
            self.history,
            corpus_tokens=self.graph.settings.full_context_token_limit + 1,
            full_context_limit=self.graph.settings.full_context_token_limit,
            provider=self.graph.local_retriever.planner_provider,
        )
        facets = state.get("missing_facets", [])
        self.plan = self.graph.planner.plan(
            self.question,
            self.history,
            prior,
            [self._facet(item) for item in facets],
            retrieval_round=state.get("retrieval_round", 0) + 1,
            web_allowed=self.web_allowed,
        )
        refined_queries = state.get("refined_queries", [])
        if refined_queries:
            self.plan = self.plan.model_copy(update={"queries": refined_queries})
        return {"retrieval_round": state.get("retrieval_round", 0) + 1}

    def search_sources(self, state: ResearchState) -> ResearchState:
        """Run bounded local then permitted Web retrieval; provider failures remain observable degradation."""
        assert self.plan is not None
        local = self._search_local()
        web = self._search_web() if self.plan.use_web else []
        return {"local_candidates": local, "web_candidates": web}

    def merge_evidence(self, state: ResearchState) -> ResearchState:
        """Deduplicate source-tagged evidence before a single rerank boundary."""
        ordered = [
            *state.get("local_candidates", []),
            *state.get("web_candidates", []),
            *state.get("wiki_candidates", []),
        ]
        unique: list[ChunkEntry] = []
        seen: set[UUID] = set()
        for chunk in ordered:
            if chunk.id not in seen:
                unique.append(chunk)
                seen.add(chunk.id)
        return {"merged_candidates": unique}

    def rerank_evidence(self, state: ResearchState) -> ResearchState:
        """Reuse the existing reranker and pack evidence under the existing token budget."""
        self.rerank_result = None
        candidates = limit_rerank_candidates(
            [RetrievalCandidate(chunk, 0.0) for chunk in state.get("merged_candidates", [])],
            self.graph.settings.retrieval_round_candidate_limit,
        )
        self.candidates = candidates
        candidate_ids = {candidate.chunk.id for candidate in candidates}
        new_evidence_found = bool(candidate_ids - self.seen_candidate_ids)
        self.seen_candidate_ids.update(candidate_ids)
        rag = [candidate for candidate in candidates if candidate.chunk.has_vector]
        lightweight = [
            candidate.chunk for candidate in candidates if not candidate.chunk.has_vector
        ]
        if rag:
            selected = (
                self.rerank_config.provider
                if self.rerank_config.version > 1
                else self.graph.settings.rerank_provider_default
            )
            started = monotonic()
            self.rerank_result = self.graph.reranker.execute(
                selected,
                self.question,
                rag,
                user_id=str(self.user.id),
                project_id=str(self.project_id),
                top_n=None,
            )
            evidence = pack_chunks(
                [item.chunk for item in self.rerank_result.candidates] + lightweight,
                self.graph.settings.retrieval_evidence_token_budget,
            )
            self.tool_calls.append(
                ToolCallTrace(
                    id=uuid4(),
                    tool_name="rerank_evidence",
                    input_summary={"candidate_count": len(rag)},
                    output_summary={
                        "provider": self.rerank_result.provider,
                        "results": len(evidence),
                        "degraded": self.rerank_result.degraded,
                    },
                    status="succeeded",
                    latency_ms=round((monotonic() - started) * 1000),
                )
            )
        else:
            evidence = pack_chunks(lightweight, self.graph.settings.retrieval_evidence_token_budget)
        return {
            "reranked_evidence": evidence,
            "final_evidence": evidence,
            "new_evidence_found": new_evidence_found,
            "source_strategy": self._strategy(state),
        }

    def judge_evidence(self, state: ResearchState) -> ResearchState:
        """Judge the reranked evidence after every bounded retrieval round."""
        assessment = self.graph.judge.assess(self.question, state.get("reranked_evidence", []))
        return self._assessment_update(assessment)

    def refine_query(self, state: ResearchState) -> ResearchState:
        """Derive a bounded second-round query from missing facets without an unbounded tool loop."""
        assert self.plan is not None
        refined = self.graph.planner.refine(
            self.question,
            [self._facet(item) for item in state.get("missing_facets", [])],
            self.plan,
            web_allowed=self.web_allowed,
        )
        self.plan = refined
        return {"refined_queries": refined.queries}

    @staticmethod
    def generate(state: ResearchState) -> ResearchState:
        """Mark retrieval completion; generation remains at the existing Ask application boundary."""
        return {}

    def _search_local(self) -> list[ChunkEntry]:
        """Delegate Hybrid RRF to the existing local retriever with the adaptive plan's safe weights."""
        assert self.plan is not None
        prior = plan_retrieval(
            self.question,
            self.history,
            corpus_tokens=self.graph.settings.full_context_token_limit + 1,
            full_context_limit=self.graph.settings.full_context_token_limit,
            provider=None,
        )
        retrieval_plan = RetrievalPlan(
            prior.route,
            tuple(self.plan.queries),
            self.plan.dense_weight,
            self.plan.lexical_weight,
            self.plan.reason,
        )
        started = monotonic()
        self.local_outcome = self.graph.local_retriever.retrieve(
            self.user,
            self.project_id,
            self.question,
            self.chunks,
            document_ids=[str(document_id) for document_id in self._document_ids()] or None,
            history=self.history,
            plan=retrieval_plan,
            allow_wiki_short_circuit=False,
        )
        self.tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="query_local_docs",
                input_summary={"query_length": len(self.question)},
                output_summary={
                    "candidates": len(self.local_outcome.candidates),
                    **self.local_outcome.metadata(),
                },
                status="degraded" if self.local_outcome.degraded else "succeeded",
                latency_ms=round((monotonic() - started) * 1000),
            )
        )
        return [candidate.chunk for candidate in self.local_outcome.candidates]

    def _search_web(self) -> list[ChunkEntry]:
        """Call Tavily only when the approved request flag and constrained plan both allow it."""
        assert self.plan is not None
        started = monotonic()
        try:
            chunks = retrieve_web(
                self.graph.web_search, self.user, self.project_id, self.plan.queries[0], limit=5
            )
        except WebEvidenceError as exc:
            self.web_degraded = True
            self.web_fallback_reason = exc.message
            chunks = []
        self.tool_calls.append(
            ToolCallTrace(
                id=uuid4(),
                tool_name="search_web",
                input_summary={"query_length": len(self.question)},
                output_summary={"results": len(chunks), "degraded": self.web_degraded},
                status="degraded" if self.web_degraded else "succeeded",
                latency_ms=round((monotonic() - started) * 1000),
            )
        )
        return chunks

    def _assessment_update(self, assessment: EvidenceAssessment) -> ResearchState:
        """Project the validated assessor output into serializable graph state."""
        return {
            "evidence_sufficient": assessment.sufficient,
            "judge_confidence": assessment.confidence,
            "needs_raw_evidence": assessment.requires_raw_evidence,
            "missing_facets": [
                facet.model_dump(mode="json") for facet in assessment.missing_facets
            ],
            "judge_degraded": assessment.degraded,
        }

    @staticmethod
    def _facet(value: dict[str, str]) -> MissingFacet:
        """Re-validate state boundary data before it reaches the adaptive planner."""
        return MissingFacet.model_validate(value)

    def _document_ids(self) -> list[UUID]:
        """Restrict personal-project vector retrieval to documents visible in this request."""
        return [chunk.document_id for chunk in self.chunks if chunk.document_id is not None]

    def _wiki_is_fresh(self) -> bool:
        """Require matching explicit generations before a Wiki-only response can short-circuit."""
        if not self.graph.settings.wiki_short_circuit_requires_fresh:
            return True
        wiki_generations = {
            metadata.get("wiki_generation")
            for chunk in self.chunks
            if isinstance(metadata := chunk.metadata, dict) and metadata.get("wiki_mode")
        }
        knowledge_generations = {
            metadata.get("knowledge_generation")
            for chunk in self.chunks
            if isinstance(metadata := chunk.metadata, dict) and not metadata.get("wiki_mode")
        }
        return (
            len(wiki_generations) == 1
            and len(knowledge_generations) == 1
            and None not in wiki_generations
            and wiki_generations == knowledge_generations
        )

    def _strategy(self, state: ResearchState) -> str:
        """Report the actual selected source combination without exposing raw evidence."""
        local = bool(state.get("local_candidates"))
        web = bool(state.get("web_candidates"))
        if local and web:
            return "hybrid_retrieval_web"
        if web:
            return "web"
        if not self.chunks:
            return "chat"
        return "hybrid_retrieval"

    def result(self, state: ResearchState) -> ResearchGraphResult:
        """Build application-facing result fields after the graph reaches its bounded terminal node."""
        strategy = state.get("source_strategy", "chat")
        return ResearchGraphResult(
            retrieved=state.get("final_evidence", []),
            candidates=self.candidates,
            retrieval_outcome=self.local_outcome,
            rerank_result=self.rerank_result,
            rerank_config=self.rerank_config,
            strategy=strategy,
            web_degraded=self.web_degraded,
            web_fallback_reason=self.web_fallback_reason,
            tool_calls=self.tool_calls,
            runtime_metadata={
                "research_graph_enabled": True,
                "retrieval_rounds": state.get("retrieval_round", 0),
                "evidence_sufficient": state.get("evidence_sufficient", False),
                "judge_confidence": state.get("judge_confidence", 0),
                "source_strategy": strategy,
                "web_allowed": self.web_allowed,
                "fallback_reasons": state.get("fallback_reasons", []),
            },
        )
