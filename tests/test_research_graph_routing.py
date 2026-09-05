"""Lock deterministic conditional routes for the index-first Research Graph."""

from __future__ import annotations

from researchmate_api.graph.routing import after_evidence, after_prepare, after_wiki


def test_small_corpus_without_wiki_plans_raw_evidence() -> None:
    """A small corpus still retrieves raw evidence instead of using an answer shortcut."""
    assert after_prepare({"corpus_tokens": 20, "web_allowed": False, "has_wiki": False}) == "plan"


def test_wiki_corpus_selects_index_before_raw_evidence_planning() -> None:
    """Wiki presence selects navigation context but cannot generate an answer directly."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 20,
                "web_allowed": False,
                "has_wiki": True,
                "wiki_fresh": True,
            }
        )
        == "select_wiki"
    )


def test_stale_wiki_corpus_plans_raw_evidence() -> None:
    """A stale Wiki cannot enter the Wiki-first branch."""
    assert (
        after_prepare(
            {
                "corpus_tokens": 20,
                "web_allowed": False,
                "has_wiki": True,
                "wiki_fresh": False,
            }
        )
        == "plan"
    )


def test_fresh_sufficient_wiki_short_circuits_only_without_raw_requirement() -> None:
    """Tier 1 is limited to fresh, confident, non-exact Wiki answers."""
    state = {
        "wiki_fresh": True,
        "evidence_sufficient": True,
        "judge_confidence": 0.9,
        "wiki_threshold": 0.8,
        "needs_raw_evidence": False,
    }

    assert after_wiki(state) == "generate"
    assert after_wiki({**state, "needs_raw_evidence": True}) == "plan"


def test_wiki_provenance_expands_before_full_rag() -> None:
    """Tier 2 uses provenance when Wiki cannot answer directly."""
    assert (
        after_wiki(
            {
                "wiki_fresh": True,
                "evidence_sufficient": False,
                "wiki_source_evidence": [object()],
            }
        )
        == "expand_sources"
    )


def test_web_permission_and_empty_corpus_keep_existing_routes() -> None:
    """Web requests plan and a no-source Ask remains chat-only."""
    assert after_prepare({"corpus_tokens": 20, "web_allowed": True, "has_wiki": False}) == "plan"
    assert after_prepare({"corpus_tokens": 0, "web_allowed": False, "has_wiki": False}) == "chat"


def test_insufficient_scoped_lightweight_evidence_uses_one_fallback() -> None:
    """Only a scoped lightweight corpus may trigger the one-shot raw-context fallback."""
    assert (
        after_evidence(
            {
                "evidence_sufficient": False,
                "has_lightweight_evidence": True,
                "lightweight_fallback_used": False,
            }
        )
        == "lightweight_fallback"
    )
    assert (
        after_evidence(
            {
                "evidence_sufficient": False,
                "has_lightweight_evidence": False,
                "lightweight_fallback_used": False,
                "missing_facets": [],
            }
        )
        == "generate"
    )


def test_fallback_does_not_repeat_and_retrieval_stays_bounded() -> None:
    """A completed fallback cannot create an unbounded loop."""
    assert (
        after_evidence(
            {
                "evidence_sufficient": False,
                "has_lightweight_evidence": True,
                "lightweight_fallback_used": True,
                "retrieval_round": 2,
                "max_retrieval_rounds": 2,
                "missing_facets": ["gap"],
            }
        )
        == "generate"
    )
