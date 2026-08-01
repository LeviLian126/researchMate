"""Provide Web retrieval, candidate diversity, and Ask execution-plan helpers."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.schemas.common import (
    CurrentUser,
    ExecutionPlan,
    SourceType,
    TaskType,
)
from researchmate_api.services.retrieval import RetrievalCandidate
from researchmate_api.services.store import ChunkEntry
from researchmate_api.services.web_search import TavilyWebSearchProvider, WebSearchRequestError


class WebEvidenceError(RuntimeError):
    """Carry a stable failure from the Web evidence boundary."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        """Record the public failure contract for the interface mapper."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def retrieve_web(
    provider: TavilyWebSearchProvider | None,
    user: CurrentUser,
    project_id: UUID,
    query: str,
    *,
    limit: int,
) -> list[ChunkEntry]:
    """Retrieve bounded Web evidence or raise an explicit provider outcome."""
    if provider is None:
        raise WebEvidenceError(
            "WEB_SEARCH_NOT_CONFIGURED",
            "Web evidence is unavailable until the search provider is configured.",
            503,
        )
    try:
        results = provider.search(
            user_id=user.id,
            project_id=project_id,
            query=query,
            limit=limit,
        )
    except WebSearchRequestError as exc:
        raise WebEvidenceError(
            "WEB_SEARCH_UNAVAILABLE",
            "The web search provider is temporarily unavailable.",
            503,
        ) from exc
    if not results:
        raise WebEvidenceError(
            "WEB_EVIDENCE_NOT_FOUND", "No usable web evidence was found.", 409
        )
    return results


def limit_rerank_candidates(
    candidates: list[RetrievalCandidate], limit: int
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
        candidate for candidate in local if candidate.chunk.id not in selected_ids
    )
    return [*diversified[:local_limit], *web[:limit]][:limit]


def build_execution_plan(
    strategy: str,
    web_enabled: bool,
    has_documents: bool,
    *,
    rerank_used: bool,
) -> ExecutionPlan:
    """Describe the tools and output schema selected for one Ask request."""
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
        output_schema="ChatAnswer" if strategy == "chat" else "GroundedAnswer",
    )
