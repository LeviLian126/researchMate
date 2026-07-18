from __future__ import annotations

import operator
from typing import Annotated, Any, Protocol, TypedDict


class EvidenceWorkflowState(TypedDict, total=False):
    run_id: str
    user_id: str
    project_id: str
    research_goal: str
    review_policy: str
    run_kind: str
    base_report_id: str
    impacted_section_keys: list[str]
    changed_document_ids: list[str]
    selected_document_ids: list[str]
    allow_web: bool
    retrieval_limit: int
    pipeline_model: str
    evidence_prompt_version: str
    pipeline_version_ref: str
    questions: list[str]
    question_index: int
    question: str
    evidence_batches: Annotated[list[dict[str, Any]], operator.add]
    claims: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    review_payload: dict[str, Any]
    decision: dict[str, Any]
    report: dict[str, Any]
    validation: dict[str, Any]


class EvidenceWorkflowDomain(Protocol):
    def plan(self, state: EvidenceWorkflowState) -> dict[str, Any]: ...

    def retrieve_and_extract(self, state: EvidenceWorkflowState) -> dict[str, Any]: ...

    def reconcile(self, state: EvidenceWorkflowState) -> dict[str, Any]: ...

    def review_payload(self, state: EvidenceWorkflowState) -> dict[str, Any] | None: ...

    def apply_decision(
        self, state: EvidenceWorkflowState, decision: dict[str, Any]
    ) -> dict[str, Any]: ...

    def synthesize(self, state: EvidenceWorkflowState) -> dict[str, Any]: ...

    def validate_and_commit(self, state: EvidenceWorkflowState) -> dict[str, Any]: ...


def build_evidence_graph(domain: EvidenceWorkflowDomain, checkpointer: Any):
    """Build the bounded graph lazily so API/unit tests do not require the worker runtime."""
    try:
        from langgraph.constants import END, START
        from langgraph.graph import StateGraph
        from langgraph.types import Send, interrupt
    except ImportError as exc:
        raise RuntimeError("LangGraph runtime is not installed") from exc

    def fan_out(state: EvidenceWorkflowState):
        return [
            Send(
                "retrieve_and_extract",
                {
                    "run_id": state["run_id"],
                    "user_id": state["user_id"],
                    "project_id": state["project_id"],
                    "research_goal": state["research_goal"],
                    "review_policy": state["review_policy"],
                    "run_kind": state.get("run_kind", "evidence_review"),
                    "base_report_id": state.get("base_report_id", ""),
                    "impacted_section_keys": state.get("impacted_section_keys", []),
                    "changed_document_ids": state.get("changed_document_ids", []),
                    "selected_document_ids": state.get("selected_document_ids", []),
                    "allow_web": state.get("allow_web", False),
                    "retrieval_limit": state.get("retrieval_limit", 12),
                    "pipeline_model": state.get("pipeline_model", ""),
                    "evidence_prompt_version": state.get("evidence_prompt_version", ""),
                    "pipeline_version_ref": state.get("pipeline_version_ref", ""),
                    "question_index": index,
                    "question": question,
                },
            )
            for index, question in enumerate(state["questions"])
        ]

    def review(state: EvidenceWorkflowState) -> dict[str, Any]:
        proposed = domain.review_payload(state)
        if proposed is None:
            return {"decision": {"decision": "approve"}}
        # Never wrap interrupt in try/except; LangGraph must persist and surface it.
        decision = interrupt(proposed)
        return domain.apply_decision({**state, "review_payload": proposed}, decision)

    builder = StateGraph(EvidenceWorkflowState)
    builder.add_node("plan", domain.plan)
    builder.add_node("retrieve_and_extract", domain.retrieve_and_extract)
    builder.add_node("reconcile", domain.reconcile)
    builder.add_node("human_review", review)
    builder.add_node("synthesize", domain.synthesize)
    builder.add_node("validate_and_commit", domain.validate_and_commit)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", fan_out, ["retrieve_and_extract"])
    builder.add_edge("retrieve_and_extract", "reconcile")
    builder.add_edge("reconcile", "human_review")
    builder.add_edge("human_review", "synthesize")
    builder.add_edge("synthesize", "validate_and_commit")
    builder.add_edge("validate_and_commit", END)
    return builder.compile(checkpointer=checkpointer)
