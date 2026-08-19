"""Provide deterministic conditional-edge decisions for Research Graph execution."""

from __future__ import annotations

from typing import Literal

from researchmate_api.graph.state import ResearchState


def after_prepare(state: ResearchState) -> Literal["chat", "select_wiki", "plan"]:
    """Route every non-empty raw corpus through index selection or evidence planning."""
    if state.get("web_allowed"):
        return "plan"
    if not state.get("corpus_tokens", 0):
        return "chat"
    return "select_wiki" if state.get("has_wiki") else "plan"


def after_evidence(state: ResearchState) -> Literal["generate", "lightweight_fallback", "refine"]:
    """End only for sufficient evidence or a bounded, non-progressing loop."""
    if state.get("evidence_sufficient"):
        return "generate"
    if state.get("has_lightweight_evidence") and not state.get("lightweight_fallback_used"):
        return "lightweight_fallback"
    if state.get("judge_degraded") or state.get("new_evidence_found") is False:
        return "generate"
    if state.get("missing_facets") == []:
        return "generate"
    if state.get("retrieval_round", 0) >= state.get("max_retrieval_rounds", 1):
        return "generate"
    return "refine"
