"""Lock deterministic conditional routes for the bounded Research Graph."""

from __future__ import annotations

from researchmate_api.graph.routing import after_evidence, after_prepare, after_wiki


def test_small_corpus_without_web_uses_full_context() -> None:
    """A bounded local corpus avoids unnecessary retrieval and reranking."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 20,
                "full_context_limit": 100,
                "web_allowed": False,
                "has_wiki": False,
            }
        )
        == "full_context"
    )


def test_web_permission_forces_planning_even_when_context_fits() -> None:
    """The explicit Web toggle authorizes and requests a Web evidence attempt."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 20,
                "full_context_limit": 100,
                "web_allowed": True,
                "has_wiki": False,
            }
        )
        == "plan"
    )


def test_empty_corpus_without_web_uses_plain_chat() -> None:
    """A chat-only Ask must not consume retrieval or judge calls."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 0,
                "full_context_limit": 100,
                "web_allowed": False,
                "has_wiki": False,
            }
        )
        == "chat"
    )


def test_large_wiki_corpus_reaches_wiki_judge() -> None:
    """Large corpora select a bounded Wiki set before evidence planning."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 200,
                "full_context_limit": 100,
                "web_allowed": False,
                "has_wiki": True,
            }
        )
        == "select_wiki"
    )


def test_fresh_confident_wiki_answer_short_circuits() -> None:
    """Only sufficient, fresh non-raw Wiki evidence can bypass raw retrieval."""
    assert (
        after_wiki(
            {
                "evidence_sufficient": True,
                "judge_confidence": 0.9,
                "wiki_threshold": 0.8,
                "wiki_fresh": True,
                "needs_raw_evidence": False,
            }
        )
        == "generate"
    )


def test_stale_wiki_cannot_short_circuit() -> None:
    """Stale Wiki material remains auxiliary context and must lead to retrieval."""
    assert (
        after_wiki(
            {
                "evidence_sufficient": True,
                "judge_confidence": 0.9,
                "wiki_threshold": 0.8,
                "wiki_fresh": False,
                "needs_raw_evidence": False,
            }
        )
        == "plan"
    )


def test_exact_request_cannot_short_circuit_on_wiki() -> None:
    """Raw-evidence policy has precedence over model confidence."""
    assert (
        after_wiki(
            {
                "evidence_sufficient": True,
                "judge_confidence": 1.0,
                "wiki_threshold": 0.8,
                "wiki_fresh": True,
                "needs_raw_evidence": True,
            }
        )
        == "plan"
    )


def test_sufficient_reranked_evidence_ends_loop() -> None:
    """The evidence judge can end retrieval before consuming the final round."""
    assert (
        after_evidence(
            {"evidence_sufficient": True, "retrieval_round": 1, "max_retrieval_rounds": 2}
        )
        == "generate"
    )


def test_insufficient_evidence_refines_when_budget_remains() -> None:
    """An insufficient first round receives exactly one bounded refinement chance."""
    assert (
        after_evidence(
            {"evidence_sufficient": False, "retrieval_round": 1, "max_retrieval_rounds": 2}
        )
        == "refine"
    )


def test_insufficient_evidence_stops_at_maximum_rounds() -> None:
    """The graph never executes an unbounded retrieval loop."""
    assert (
        after_evidence(
            {"evidence_sufficient": False, "retrieval_round": 2, "max_retrieval_rounds": 2}
        )
        == "generate"
    )


def test_degraded_judge_and_repeated_evidence_end_the_loop_early() -> None:
    """An unavailable judge or unchanged evidence cannot spend a redundant second round."""
    assert (
        after_evidence(
            {
                "evidence_sufficient": False,
                "judge_degraded": True,
                "retrieval_round": 1,
                "max_retrieval_rounds": 2,
            }
        )
        == "generate"
    )
    assert (
        after_evidence(
            {
                "evidence_sufficient": False,
                "new_evidence_found": False,
                "retrieval_round": 1,
                "max_retrieval_rounds": 2,
            }
        )
        == "generate"
    )
