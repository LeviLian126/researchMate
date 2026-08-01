"""Own local evidence selection, scope-aware search, and explicit degradation results."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from researchmate_api.config import Settings
from researchmate_api.schemas.common import CurrentUser, SourceType
from researchmate_api.services.qdrant_store import QdrantHybridStore, VectorStoreRequestError
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
    strategy: str
    full_context: bool
    estimated_tokens: int
    degraded: bool = False
    reason: str | None = None


class LocalEvidenceRetriever:
    """Combine lexical and semantic retrieval without bypassing relevance gates."""

    def __init__(
        self,
        settings: Settings,
        repository: ResearchMateRepository,
        hybrid_store: QdrantHybridStore | None,
    ) -> None:
        """Bind retrieval configuration and the two storage boundaries."""
        self.settings = settings
        self.repository = repository
        self.hybrid_store = hybrid_store

    def retrieve(
        self,
        user: CurrentUser,
        project_id: UUID,
        query: str,
        chunks: list[ChunkEntry],
        *,
        document_ids: list[str] | None = None,
    ) -> RetrievalOutcome:
        """Select relevant evidence before deciding how much selected context fits."""
        lexical = bm25_candidates(chunks, query, limit=30)
        semantic, degraded, reason = self._semantic_candidates(
            user, project_id, query, document_ids=document_ids
        )
        candidates = fuse_candidates(
            lexical,
            semantic,
            limit=self.settings.rerank_candidate_limit,
        )
        selected_tokens = sum(estimate_tokens(item.chunk.text) for item in candidates)
        full_context = bool(candidates) and selected_tokens <= self.settings.full_context_token_limit
        return RetrievalOutcome(
            candidates=candidates,
            strategy="full_context" if full_context else "hybrid_retrieval",
            full_context=full_context,
            estimated_tokens=selected_tokens,
            degraded=degraded,
            reason=reason,
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

    def _semantic_candidates(
        self,
        user: CurrentUser,
        project_id: UUID,
        query: str,
        *,
        document_ids: list[str] | None,
    ) -> tuple[list[ChunkEntry], bool, str | None]:
        """Return vector candidates and expose provider failures as degraded retrieval."""
        if self.hybrid_store is None:
            return [], False, None
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
            return [], True, "semantic_retrieval_unavailable"
        ids: list[UUID] = []
        for match in matches:
            try:
                ids.append(UUID(str(match["payload"]["chunk_id"])))
            except (KeyError, TypeError, ValueError):
                continue
        return self.repository.get_chunks_by_ids(user, project_id, ids) or [], False, None
