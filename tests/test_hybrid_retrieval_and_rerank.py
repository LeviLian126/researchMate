from datetime import UTC, datetime
from uuid import uuid4

from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.grounded_query import GroundedQueryService
from researchmate_api.services.rerank import NvidiaReranker, RerankCoordinator
from researchmate_api.services.retrieval import (
    RetrievalCandidate,
    bm25_candidates,
    fuse_candidates,
    pack_chunks,
    tokenize,
)
from researchmate_api.services.store import ChunkEntry


def _chunk(text: str, title: str = "notes.md") -> ChunkEntry:
    return ChunkEntry(
        id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        source_type=SourceType.LOCAL_DOC,
        source_title=title,
        text=text,
        created_at=datetime.now(UTC),
    )


def test_mixed_tokenizer_keeps_identifiers_and_chinese_bigrams() -> None:
    tokens = tokenize("Qdrant multi_vector 支持中文检索 v1/ranking")
    assert "multi_vector" in tokens
    assert "v1/ranking" in tokens
    assert "中文" in tokens
    assert "检索" in tokens


def test_bm25_weights_exact_phrase_title_and_repeated_hits() -> None:
    exact = _chunk("Use runtime config for hot reload. runtime config is versioned.", "Rerank")
    loose = _chunk("A runtime can reload configuration.")
    unrelated = _chunk("Deployment rollback guide.")
    ranked = bm25_candidates([loose, unrelated, exact], "runtime config")
    assert ranked[0].chunk.id == exact.id
    assert all(item.chunk.id != unrelated.id for item in ranked)


def test_rrf_deduplicates_and_rewards_cross_channel_hits() -> None:
    shared, lexical_only, semantic_only = _chunk("shared"), _chunk("lexical"), _chunk("semantic")
    lexical = [
        RetrievalCandidate(shared, 10, lexical_rank=1),
        RetrievalCandidate(lexical_only, 8, lexical_rank=2),
    ]
    fused = fuse_candidates(lexical, [semantic_only, shared], limit=3)
    assert fused[0].chunk.id == shared.id
    assert len({item.chunk.id for item in fused}) == 3


def test_context_packer_respects_budget_after_first_item() -> None:
    first = _chunk("a " * 20)
    oversized = _chunk("b " * 200)
    last = _chunk("c " * 20)
    packed = pack_chunks([first, oversized, last], token_budget=70)
    assert [item.id for item in packed] == [first.id, last.id]


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"rankings": [{"index": 1}, {"index": 0}]}


class _NvidiaClient:
    def __init__(self) -> None:
        self.payload = None

    def post(self, path: str, *, json: dict):
        assert path == "/v1/ranking"
        self.payload = json
        return _Response()


def test_nvidia_adapter_uses_ranking_api_and_top_n() -> None:
    client = _NvidiaClient()
    settings = Settings(nvidia_api_key="secret", nvidia_rerank_model="rank-model")
    reranker = NvidiaReranker(settings, client=client)
    candidates = [
        RetrievalCandidate(_chunk("first"), 1),
        RetrievalCandidate(_chunk("second"), 0.5),
    ]
    result = reranker.rerank(
        "query", candidates, top_n=2, user_id="user", project_id="project"
    )
    assert [item.chunk.text for item in result] == ["second", "first"]
    assert client.payload["model"] == "rank-model"
    assert client.payload["top_n"] == 2


def test_auto_provider_degrades_deterministically_when_models_unavailable() -> None:
    coordinator = RerankCoordinator(
        Settings(
            _env_file=None,
            llm_provider="fake",
            embedding_provider="fake",
            web_search_provider="disabled",
            nvidia_api_key=None,
        ),
        qdrant=None,
    )
    candidates = [RetrievalCandidate(_chunk("candidate"), 0.25)]
    result = coordinator.execute(
        "auto", "query", candidates, user_id="user", project_id="project"
    )
    assert result.provider == "deterministic"
    assert result.degraded is True
    assert "nvidia_unavailable" in (result.fallback_reason or "")


def test_provider_candidate_limit_preserves_web_and_document_diversity() -> None:
    first, second = _chunk("first"), _chunk("second")
    repeated = _chunk("repeat")
    repeated.document_id = first.document_id
    web = _chunk("web")
    web.source_type = SourceType.WEB_PAGE
    web.document_id = None
    limited = GroundedQueryService._limit_rerank_candidates(
        [
            RetrievalCandidate(first, 1),
            RetrievalCandidate(repeated, 0.9),
            RetrievalCandidate(second, 0.8),
            RetrievalCandidate(web, 0.7),
        ],
        3,
    )
    assert len(limited) == 3
    assert web.id in {candidate.chunk.id for candidate in limited}
    assert {first.document_id, second.document_id}.issubset(
        {candidate.chunk.document_id for candidate in limited}
    )
