"""Provide deterministic lexical retrieval, token estimates, and hard context packing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
from re import findall
from uuid import UUID

from researchmate_api.services.store import ChunkEntry


def tokenize(text: str) -> list[str]:
    """Tokenize identifiers, Latin words, CJK characters, and adjacent CJK bigrams."""
    normalized = text.lower()
    words = findall(r"[a-z0-9_./:-]+", normalized)
    cjk_runs = findall(r"[\u3400-\u9fff]+", normalized)
    cjk_tokens: list[str] = []
    for run in cjk_runs:
        cjk_tokens.extend(run)
        cjk_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return words + cjk_tokens


def estimate_tokens(text: str) -> int:
    """Return a conservative provider-neutral token estimate for mixed text."""
    latin = findall(r"[a-zA-Z0-9_./:-]+", text)
    cjk = findall(r"[\u3400-\u9fff]", text)
    other_chars = max(0, len(text) - sum(map(len, latin)) - len(cjk))
    return max(1, int(len(latin) * 1.35 + len(cjk) + other_chars / 4))


@dataclass(frozen=True)
class RetrievalCandidate:
    """Carry one chunk with its fused and provider-specific ranks."""

    chunk: ChunkEntry
    score: float
    lexical_rank: int | None = None
    semantic_rank: int | None = None


def bm25_candidates(
    chunks: list[ChunkEntry],
    query: str,
    *,
    limit: int = 30,
) -> list[RetrievalCandidate]:
    """Rank chunks with a bounded BM25-style lexical score."""
    query_tokens = Counter(tokenize(query))
    if not query_tokens or not chunks:
        return []
    documents = [tokenize(f"{chunk.source_title} {chunk.text}") for chunk in chunks]
    lengths = [max(1, len(tokens)) for tokens in documents]
    average_length = sum(lengths) / len(lengths)
    document_frequency = Counter(
        token for tokens in documents for token in set(tokens) if token in query_tokens
    )
    query_normalized = " ".join(query.lower().split())
    scored: list[tuple[float, int, ChunkEntry]] = []
    for index, (chunk, tokens, length) in enumerate(zip(chunks, documents, lengths, strict=True)):
        counts = Counter(tokens)
        score = 0.0
        for token, query_count in query_tokens.items():
            frequency = counts[token]
            if not frequency:
                continue
            inverse_frequency = log(
                1
                + (len(chunks) - document_frequency[token] + 0.5)
                / (document_frequency[token] + 0.5)
            )
            denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * length / average_length)
            score += inverse_frequency * (frequency * 2.2 / denominator) * min(query_count, 2)
        compact = " ".join(chunk.text.lower().split())
        if query_normalized and query_normalized in compact:
            score += 4.0
        title = chunk.source_title.lower()
        score += sum(0.75 for token in query_tokens if token in title)
        if score > 0:
            scored.append((score, -index, chunk))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        RetrievalCandidate(chunk=chunk, score=score, lexical_rank=rank)
        for rank, (score, _, chunk) in enumerate(scored[:limit], start=1)
    ]


def fuse_candidates(
    lexical: list[RetrievalCandidate],
    semantic_chunks: list[ChunkEntry],
    *,
    limit: int = 50,
    rrf_k: int = 60,
) -> list[RetrievalCandidate]:
    """Fuse lexical and semantic ranks with reciprocal-rank fusion."""
    by_id: dict[UUID, RetrievalCandidate] = {}
    scores: Counter[UUID] = Counter()
    for candidate in lexical:
        rank = candidate.lexical_rank or 1
        scores[candidate.chunk.id] += 1 / (rrf_k + rank)
        by_id[candidate.chunk.id] = candidate
    for rank, chunk in enumerate(semantic_chunks, start=1):
        scores[chunk.id] += 1 / (rrf_k + rank)
        previous = by_id.get(chunk.id)
        by_id[chunk.id] = RetrievalCandidate(
            chunk=chunk,
            score=0,
            lexical_rank=previous.lexical_rank if previous else None,
            semantic_rank=rank,
        )
    ranked_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)[:limit]
    return [
        RetrievalCandidate(
            chunk=by_id[chunk_id].chunk,
            score=scores[chunk_id],
            lexical_rank=by_id[chunk_id].lexical_rank,
            semantic_rank=by_id[chunk_id].semantic_rank,
        )
        for chunk_id in ranked_ids
    ]


def pack_chunks(chunks: list[ChunkEntry], token_budget: int) -> list[ChunkEntry]:
    """Pack whole chunks without allowing even the first chunk to exceed the budget."""
    packed: list[ChunkEntry] = []
    used = 0
    if token_budget <= 0:
        return packed
    for chunk in chunks:
        size = estimate_tokens(chunk.text)
        if used + size > token_budget:
            continue
        packed.append(chunk)
        used += size
        if used >= token_budget:
            break
    return packed


def retrieve_local_chunks(chunks: list[ChunkEntry], query: str, limit: int = 5) -> list[ChunkEntry]:
    """Preserve the local fallback boundary with BM25 rather than token overlap."""
    return [candidate.chunk for candidate in bm25_candidates(chunks, query, limit=limit)]


def snippet(text: str, length: int = 280) -> str:
    """Collapse whitespace and return a display-safe bounded evidence excerpt."""
    compact = " ".join(text.split())
    if len(compact) <= length:
        return compact
    return compact[: length - 1].rstrip() + "…"
