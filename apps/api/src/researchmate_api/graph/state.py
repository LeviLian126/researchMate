"""Define the explicit state carried through the bounded Research Graph."""

from __future__ import annotations

from typing import TypedDict

from researchmate_api.services.store import ChunkEntry


class ResearchState(TypedDict, total=False):
    """Carry request-scoped evidence and control state without durable checkpointing."""

    question: str
    corpus_tokens: int
    full_context_limit: int
    wiki_threshold: float
    has_wiki: bool
    web_allowed: bool
    wiki_candidates: list[ChunkEntry]
    wiki_fresh: bool
    needs_raw_evidence: bool
    local_candidates: list[ChunkEntry]
    web_candidates: list[ChunkEntry]
    merged_candidates: list[ChunkEntry]
    reranked_evidence: list[ChunkEntry]
    final_evidence: list[ChunkEntry]
    retrieval_round: int
    max_retrieval_rounds: int
    evidence_sufficient: bool
    judge_confidence: float
    missing_facets: list[dict[str, str]]
    source_strategy: str
    degraded: bool
    fallback_reasons: list[str]
