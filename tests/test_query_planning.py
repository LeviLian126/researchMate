"""Verify observable retrieval routes and bounded query expansion."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from researchmate_api.schemas.conversation import ConversationMessage
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.query_planning import RetrievalRoute, plan_retrieval


class _Planner:
    """Return one deterministic structured expansion."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: object) -> LLMResult:
        self.calls += 1
        return LLMResult(
            content=(
                '{"standalone_query":"Qdrant BM25 如何融合 dense 检索",'
                '"variants":["Qdrant weighted RRF BM25 dense"]}'
            ),
            reasoning=None,
            model="fake",
            prompt_tokens=10,
            completion_tokens=10,
        )


def _history(content: str) -> ConversationMessage:
    return ConversationMessage(
        id=uuid4(),
        conversation_id=uuid4(),
        role="user",
        content=content,
        created_at=datetime.now(UTC),
    )


def test_router_uses_full_context_only_for_the_entire_corpus() -> None:
    """Base full-context selection on all authorized chunks, not top candidates."""
    plan = plan_retrieval(
        "summarize",
        [],
        corpus_tokens=12001,
        full_context_limit=12000,
        provider=None,
    )
    assert plan.route != RetrievalRoute.FULL_CONTEXT


def test_router_weights_exact_and_semantic_intents_differently() -> None:
    """Expose meaningful route-specific channel policy."""
    exact = plan_retrieval(
        "Find RFC-9110 section 9.3",
        [],
        corpus_tokens=20000,
        full_context_limit=12000,
        provider=None,
    )
    semantic = plan_retrieval(
        "为什么混合检索比单路召回稳定？",
        [],
        corpus_tokens=20000,
        full_context_limit=12000,
        provider=None,
    )
    assert exact.route == RetrievalRoute.EXACT
    assert exact.lexical_weight > exact.dense_weight
    assert semantic.route == RetrievalRoute.SEMANTIC
    assert semantic.dense_weight > semantic.lexical_weight


def test_follow_up_expands_once_and_preserves_original_query() -> None:
    """Resolve references with one call while retaining the user's literal wording."""
    provider = _Planner()
    question = "那它和 dense 是怎么融合的？"
    plan = plan_retrieval(
        question,
        [_history("Explain Qdrant BM25")],
        corpus_tokens=20000,
        full_context_limit=12000,
        provider=provider,
    )
    assert plan.route == RetrievalRoute.EXPANDED_HYBRID
    assert provider.calls == 1
    assert plan.queries[0] == question
    assert len(plan.queries) <= 3


def test_planner_failure_degrades_to_the_original_query() -> None:
    """Keep retrieval available when optional expansion is not configured."""
    question = "那它呢？"
    plan = plan_retrieval(
        question,
        [_history("Explain hybrid retrieval")],
        corpus_tokens=20000,
        full_context_limit=12000,
        provider=None,
    )
    assert plan.degraded is True
    assert plan.queries == (question,)
