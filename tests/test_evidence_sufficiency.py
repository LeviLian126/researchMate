"""Verify fail-closed structured evidence and adaptive-planning boundaries."""

from __future__ import annotations

from uuid import UUID

from researchmate_api.config import Settings
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.adaptive_query_planning import AdaptiveQueryPlanner
from researchmate_api.services.evidence_sufficiency import (
    EvidenceReasonCode,
    EvidenceSufficiencyService,
    requires_raw_evidence,
)
from researchmate_api.services.query_planning import RetrievalPlan, RetrievalRoute
from researchmate_api.services.store import ChunkEntry


def _settings() -> Settings:
    """Create a local settings object without an external provider."""
    return Settings(app_env="test", llm_provider="fake", embedding_provider="fake")


def _prior() -> RetrievalPlan:
    """Build the existing deterministic plan used as the adaptive fallback."""
    return RetrievalPlan(
        RetrievalRoute.HYBRID,
        ("retrieval weights",),
        dense_weight=0.5,
        lexical_weight=0.5,
        reason="balanced_default",
    )


def test_exactness_policy_requires_raw_evidence() -> None:
    """Identifiers, numeric values, and source checks bypass Wiki-only answers."""
    assert requires_raw_evidence("What is the exact RRF config value 0.7?") is True
    assert requires_raw_evidence("Explain hybrid retrieval") is False


def test_unconfigured_judge_fails_closed_to_retrieval() -> None:
    """An unavailable judge cannot claim a supplied Wiki page is sufficient."""
    assessment = EvidenceSufficiencyService(None).assess(
        "Explain retrieval",
        [
            ChunkEntry(
                id=UUID("00000000-0000-4000-8000-000000000010"),
                user_id=UUID("00000000-0000-4000-8000-000000000011"),
                project_id=UUID("00000000-0000-4000-8000-000000000012"),
                document_id=None,
                source_type=SourceType.LOCAL_DOC,
                source_title="wiki",
                text="A Wiki summary.",
                metadata={"wiki_mode": True},
            )
        ],
    )
    assert assessment.sufficient is False
    assert assessment.reason_code == EvidenceReasonCode.MISSING_DETAIL


def test_adaptive_fallback_preserves_prior_and_honors_web_permission() -> None:
    """Planner outages retain deterministic Local RRF and request authorized Web evidence."""
    plan = AdaptiveQueryPlanner(_settings(), None).plan(
        "retrieval weights",
        [],
        _prior(),
        [],
        retrieval_round=1,
        web_allowed=True,
    )
    assert plan.queries == ["retrieval weights"]
    assert plan.use_local is True
    assert plan.use_web is True
    assert plan.dense_weight + plan.lexical_weight == 1
