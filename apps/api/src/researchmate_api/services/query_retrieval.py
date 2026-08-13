"""Own local evidence selection, scope-aware search, and explicit degradation results."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from researchmate_api.config import Settings
from researchmate_api.schemas.common import ContextStrategy, CurrentUser, SourceType
from researchmate_api.schemas.conversation import ConversationMessage
from researchmate_api.services.llm import ChatProvider
from researchmate_api.services.qdrant_store import QdrantHybridStore, VectorStoreRequestError
from researchmate_api.services.query_planning import RetrievalPlan, RetrievalRoute, plan_retrieval
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    bm25_candidates,
    estimate_tokens,
    fuse_candidates,
)
from researchmate_api.services.scope_policy import require_workspace_scope
from researchmate_api.services.store import ChunkEntry, ResearchMateRepository


@dataclass(frozen=True)
class RetrievalOutcome:
    """Describe selected candidates and whether the semantic path degraded."""

    candidates: list[RetrievalCandidate]
    strategy: ContextStrategy
    full_context: bool
    estimated_tokens: int
    route: RetrievalRoute = RetrievalRoute.HYBRID
    route_reason: str = "balanced_default"
    query_count: int = 1
    dense_weight: float = 0.5
    lexical_weight: float = 0.5
    planner_degraded: bool = False
    degraded: bool = False
    reason: str | None = None

    def metadata(self, *, prefix: str = "") -> dict[str, object]:
        """Expose the observable routing decision with an optional key prefix."""
        return {
            f"{prefix}route": self.route.value,
            f"{prefix}route_reason": self.route_reason,
            f"{prefix}query_count": self.query_count,
            f"{prefix}dense_weight": self.dense_weight,
            f"{prefix}lexical_weight": self.lexical_weight,
            f"{prefix}planner_degraded": self.planner_degraded,
        }


class LocalEvidenceRetriever:
    """Combine lexical and semantic retrieval without bypassing relevance gates."""

    def __init__(
        self,
        settings: Settings,
        repository: ResearchMateRepository,
        hybrid_store: QdrantHybridStore | None,
        planner_provider: ChatProvider | None = None,
    ) -> None:
        """Bind retrieval configuration and the two storage boundaries."""
        self.settings = settings
        self.repository = repository
        self.hybrid_store = hybrid_store
        self.planner_provider = planner_provider

    def retrieve(
        self,
        user: CurrentUser,
        project_id: UUID,
        query: str,
        chunks: list[ChunkEntry],
        *,
        document_ids: list[str] | None = None,
        history: list[ConversationMessage] | None = None,
    ) -> RetrievalOutcome:
        """Route the complete authorized corpus, then retrieve or use it in full."""
        lightweight_chunks = [c for c in chunks if not c.has_vector]
        rag_chunks = [c for c in chunks if c.has_vector]
        corpus_tokens = sum(estimate_tokens(chunk.text) for chunk in chunks)
        plan = plan_retrieval(
            query,
            history or [],
            corpus_tokens=corpus_tokens,
            full_context_limit=self.settings.full_context_token_limit,
            provider=self.planner_provider,
        )
        if plan.route == RetrievalRoute.FULL_CONTEXT:
            relevance = bm25_candidates(chunks, query, limit=1)
            general_request = any(
                marker in query.casefold()
                for marker in ("summarize", "summary", "总结", "概括", "这份资料", "文档内容")
            )
            candidates = (
                [RetrievalCandidate(chunk, 1.0) for chunk in chunks]
                if relevance or general_request
                else []
            )
            return self._outcome(candidates, plan, corpus_tokens=corpus_tokens)

        if rag_chunks:
            candidates, degraded, reason = self._hybrid_candidates(
                user,
                project_id,
                plan,
                rag_chunks,
                document_ids=document_ids,
            )
        else:
            candidates, degraded, reason = [], False, "all_lightweight_corpus"
        candidates.extend(
            RetrievalCandidate(chunk=chunk, score=0.0) for chunk in lightweight_chunks
        )
        selected_tokens = sum(estimate_tokens(item.chunk.text) for item in candidates)
        return RetrievalOutcome(
            candidates=candidates,
            strategy="hybrid_retrieval",
            full_context=False,
            estimated_tokens=selected_tokens,
            route=plan.route,
            route_reason=plan.reason,
            query_count=len(plan.queries),
            dense_weight=plan.dense_weight,
            lexical_weight=plan.lexical_weight,
            planner_degraded=plan.degraded,
            degraded=degraded or plan.degraded,
            reason=reason,
        )

    @staticmethod
    def _outcome(
        candidates: list[RetrievalCandidate],
        plan: RetrievalPlan,
        *,
        corpus_tokens: int,
    ) -> RetrievalOutcome:
        """Build a full-context outcome without pretending selected candidates are the corpus."""
        usable = bool(candidates)
        return RetrievalOutcome(
            candidates=candidates,
            strategy="full_context" if usable else "hybrid_retrieval",
            full_context=usable,
            estimated_tokens=corpus_tokens,
            route=plan.route,
            route_reason=plan.reason,
            query_count=1,
            dense_weight=0.0,
            lexical_weight=0.0,
        )

    def search_workspace(
        self, user: CurrentUser, project_id: UUID, query: str, limit: int
    ) -> list[ChunkEntry]:
        """Search only an owned workspace; personal projects require a conversation."""
        project = self.repository.get_project(user, project_id)
        if project is None or project.status != "active":
            return []
        require_workspace_scope(project)
        chunks = self.repository.project_chunks(user, project_id) or []
        return [item.chunk for item in bm25_candidates(chunks, query, limit=limit)]

    def search_conversation(
        self,
        user: CurrentUser,
        project_id: UUID,
        conversation_id: UUID,
        query: str,
        limit: int,
    ) -> list[ChunkEntry] | None:
        """Search chunks that belong to one owned personal conversation only."""
        project = self.repository.get_project(user, project_id)
        if project is None or project.status != "active":
            return None
        chunks = self.repository.conversation_chunks(user, project_id, conversation_id)
        if chunks is None:
            return None
        return [item.chunk for item in bm25_candidates(chunks, query, limit=limit)]

    def _hybrid_candidates(
        self,
        user: CurrentUser,
        project_id: UUID,
        plan: RetrievalPlan,
        chunks: list[ChunkEntry],
        *,
        document_ids: list[str] | None,
    ) -> tuple[list[RetrievalCandidate], bool, str | None]:
        """Use the native hybrid store and fall back to bounded application BM25."""
        if self.hybrid_store is None:
            return (
                bm25_candidates(
                    chunks, plan.queries[0], limit=self.settings.rerank_candidate_limit
                ),
                True,
                "hybrid_store_unconfigured",
            )
        if not self.settings.qdrant_native_hybrid_enabled:
            lexical = bm25_candidates(
                chunks, plan.queries[0], limit=self.settings.rerank_candidate_limit
            )
            try:
                matches = self.hybrid_store.query_dense(
                    user_id=str(user.id),
                    project_id=str(project_id),
                    source_type=SourceType.LOCAL_DOC,
                    text=plan.queries[0],
                    limit=self.settings.rerank_candidate_limit,
                    document_ids=document_ids,
                )
                semantic = self._hydrate_matches(user, project_id, matches)
            except VectorStoreRequestError:
                return lexical, True, "legacy_dense_unavailable_application_bm25_used"
            return (
                fuse_candidates(
                    lexical,
                    [candidate.chunk for candidate in semantic],
                    limit=self.settings.rerank_candidate_limit,
                ),
                False,
                "legacy_hybrid_rollback_mode",
            )
        try:
            matches = self.hybrid_store.query(
                user_id=str(user.id),
                project_id=str(project_id),
                source_type=SourceType.LOCAL_DOC,
                text=plan.queries[0],
                limit=self.settings.rerank_candidate_limit,
                document_ids=document_ids,
                plan=plan,
            )
        except VectorStoreRequestError:
            return (
                bm25_candidates(
                    chunks, plan.queries[0], limit=self.settings.rerank_candidate_limit
                ),
                True,
                "native_hybrid_unavailable_application_bm25_used",
            )
        return self._hydrate_matches(user, project_id, matches), False, None

    def _hydrate_matches(
        self,
        user: CurrentUser,
        project_id: UUID,
        matches: list[dict[str, object]],
    ) -> list[RetrievalCandidate]:
        """Hydrate owner-filtered vector identities while preserving provider rank."""
        ids: list[UUID] = []
        scores: dict[UUID, float] = {}
        for match in matches:
            try:
                payload = match["payload"]
                if not isinstance(payload, dict):
                    continue
                chunk_id = UUID(str(payload["chunk_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            ids.append(chunk_id)
            raw_score = match.get("score", 0.0)
            scores[chunk_id] = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
        hydrated = self.repository.get_chunks_by_ids(user, project_id, ids) or []
        by_id = {chunk.id: chunk for chunk in hydrated}
        ranked = [
            RetrievalCandidate(
                chunk=by_id[chunk_id],
                score=scores[chunk_id],
                semantic_rank=rank,
            )
            for rank, chunk_id in enumerate(ids, start=1)
            if chunk_id in by_id
        ]
        return ranked
