from __future__ import annotations


def test_langgraph_graph_executes_a_bounded_local_path() -> None:
    from researchmate_worker.evidence_graph import build_evidence_graph

    class Domain:
        def plan(self, _state):
            return {"questions": ["first", "second"]}

        def retrieve_and_extract(self, state):
            return {"evidence_batches": [{"question": state["question"], "claims": []}]}

        def reconcile(self, _state):
            return {"claims": [], "relations": []}

        def review_payload(self, _state):
            return None

        def apply_decision(self, _state, decision):
            return {"decision": decision}

        def synthesize(self, _state):
            return {"report": {"title": "safe local proof"}}

        def validate_and_commit(self, _state):
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
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.postgres import PostgresSaver
    from ragas.llms import llm_factory
    from ragas.metrics.collections import Faithfulness

    serializer = JsonPlusSerializer(pickle_fallback=False)

    assert serializer is not None
    assert PostgresSaver is not None
    assert llm_factory is not None
    assert Faithfulness is not None
