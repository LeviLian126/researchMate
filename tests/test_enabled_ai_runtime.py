"""Verify pinned AI runtime dependencies support the bounded local contracts."""

from __future__ import annotations


def test_langgraph_graph_executes_a_bounded_local_path() -> None:
    """Exercise one bounded network-free LangGraph path."""
    from researchmate_worker.evidence_graph import build_evidence_graph

    class Domain:
        def plan(self, _state: object) -> dict[str, list[str]]:
            return {"questions": ["first", "second"]}

        def retrieve_and_extract(self, state: dict[str, object]) -> dict[str, list[dict[str, object]]]:
            return {"evidence_batches": [{"question": state["question"], "claims": []}]}

        def reconcile(self, _state: object) -> dict[str, list[object]]:
            return {"claims": [], "relations": []}

        def review_payload(self, _state: object) -> None:
            return None

        def apply_decision(self, _state: object, decision: object) -> dict[str, object]:
            return {"decision": decision}

        def synthesize(self, _state: object) -> dict[str, dict[str, str]]:
            return {"report": {"title": "safe local proof"}}

        def validate_and_commit(self, _state: object) -> dict[str, dict[str, str]]:
            return {"validation": {"status": "passed"}}

    graph = build_evidence_graph(Domain(), None)
    result = graph.invoke(
        {
            "run_id": "run",
            "user_id": "user",
            "project_id": "project",
            "research_goal": "goal",
            "review_policy": "strict",
            "evidence_batches": [],
        }
    )

    assert result["validation"] == {"status": "passed"}
    assert len(result["evidence_batches"]) == 2
    assert result["decision"] == {"decision": "approve"}


def test_ragas_and_strict_checkpoint_serializer_import_with_pinned_compatibility() -> None:
    """Require pinned evaluation and checkpoint serializer compatibility."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from ragas.llms import llm_factory
    from ragas.metrics.collections import Faithfulness

    serializer = JsonPlusSerializer(pickle_fallback=False)

    assert serializer is not None
    assert PostgresSaver is not None
    assert llm_factory is not None
    assert Faithfulness is not None
