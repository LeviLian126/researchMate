"""Provide deterministic conditional-edge decisions for Research Graph execution."""

from __future__ import annotations

from typing import Literal

from researchmate_api.graph.state import ResearchState


def after_prepare(state: ResearchState) -> Literal["full_context", "select_wiki", "plan"]:
    """Route small corpora directly while keeping empty corpora on the planning path."""
    if state.get("web_allowed"):
        return "plan"
    if state.get("has_wiki"):
        return "select_wiki"
    if state.get("corpus_tokens", 0) and state["corpus_tokens"] <= state["full_context_limit"]:  # type: ignore[typeddict-item]
        return "full_context"
    return "select_wiki" if state.get("has_wiki") else "plan"  # type: ignore[return-value]


def after_wiki(state: ResearchState) -> Literal["generate", "plan"]:
    """Permit a Wiki-only answer only after all deterministic safety gates pass."""
    if (
        state.get("evidence_sufficient")
        and state.get("judge_confidence", 0) >= state["wiki_threshold"]  # type: ignore[typeddict-item]
        and state.get("wiki_fresh")
        and not state.get("needs_raw_evidence")
    ):
        return "generate"
    return "plan"


def after_evidence(state: ResearchState) -> Literal["generate", "refine"]:
    """End only for sufficient evidence or a bounded, non-progressing loop."""
    if state.get("evidence_sufficient"):
        return "generate"
    if state.get("retrieval_round", 0) >= state.get("max_retrieval_rounds", 1):
        return "generate"
    return "refine"
