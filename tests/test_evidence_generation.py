"""Verify evidence generation accepts only server-issued identifiers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.evidence_generation import (
    EvidenceGenerationError,
    build_research_plan,
    extract_claims,
    reconcile_claims,
    synthesize_report,
)
from researchmate_api.services.llm import LLMResult
from researchmate_api.services.store import ChunkEntry


class FakeProvider:
    """Return deterministic structured outputs to generation services."""

    def __init__(self, outputs: list[Any]) -> None:  # boundary: opaque LLM output
        self.outputs = iter(outputs)

    def complete(self, messages: object) -> LLMResult:
        return LLMResult(
            content=json.dumps(next(self.outputs)),
            reasoning=None,
            model="fake",
            prompt_tokens=1,
            completion_tokens=1,
        )


def chunk() -> ChunkEntry:
    """Create a representative server-owned evidence chunk."""
    return ChunkEntry(
        id=UUID(int=1),
        user_id=UUID(int=2),
        project_id=UUID(int=3),
        document_id=UUID(int=4),
        source_type=SourceType.LOCAL_DOC,
        source_title="source",
        text="The evidence supports claim A.",
        page_no=2,
    )


def test_evidence_generation_pipeline_accepts_only_server_ids() -> None:
    """Accept plans, claims, relations, and reports using allowlisted IDs."""
    provider = FakeProvider(
        [
            {"questions": ["What supports A?", "What contradicts A?"]},
            {
                "claims": [
                    {
                        "text": "A is supported.",
                        "stance": "supports",
                        "confidence": 0.9,
                        "evidence_ids": [1],
                    }
                ]
            },
            {
                "title": "Review",
                "sections": [
                    {
                        "section_key": "finding",
                        "heading": "Finding",
                        "body_markdown": "A is supported.",
                        "claim_ids": [1],
                    }
                ],
            },
        ]
    )
    plan = build_research_plan(provider, "Review A")
    claims = extract_claims(provider, plan.questions[0], [chunk()])
    report = synthesize_report(provider, "Review A", claims.claims)

    assert len(plan.questions) == 2
    assert claims.claims[0].evidence_ids == [1]
    assert report.sections[0].claim_ids == [1]


def test_claim_extraction_rejects_unknown_evidence_ids() -> None:
    """Reject provider claims that reference unknown evidence."""
    provider = FakeProvider(
        [
            {
                "claims": [
                    {
                        "text": "Unsupported reference.",
                        "stance": "neutral",
                        "confidence": 0.5,
                        "evidence_ids": [2],
                    }
                ]
            }
        ]
    )

    with pytest.raises(EvidenceGenerationError):
        extract_claims(provider, "question", [chunk()])


def test_reconciliation_rejects_self_edges() -> None:
    """Reject provider relations that point a claim to itself."""
    claim = SimpleNamespace(text="A", stance="neutral")
    provider = FakeProvider(
        [
            {
                "relations": [
                    {
                        "source_claim_id": 1,
                        "target_claim_id": 1,
                        "relation": "duplicates",
                        "confidence": 1,
                        "rationale_summary": "same",
                    }
                ]
            }
        ]
    )

    with pytest.raises(EvidenceGenerationError):
        reconcile_claims(provider, [claim, claim])
