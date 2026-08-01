"""Exercise evidence-workflow planning and owned-evidence retrieval decisions."""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from researchmate_api.schemas.common import SourceType
from researchmate_api.services.evidence_generation import (
    ClaimBatch,
    ExtractedClaim,
    ResearchPlan,
)
from researchmate_api.services.store import ChunkEntry
from researchmate_worker import workflow_runtime
from researchmate_worker.workflow_runtime import (
    SqlEvidenceWorkflowDomain,
    WorkflowPipelineConfig,
    WorkflowRuntimeError,
)

RUN_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000102")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000103")
CHUNK_ID = UUID("00000000-0000-4000-8000-000000000104")


class FakeResult:
    """Provides the small SQLAlchemy result surface used by workflow methods."""

    def __init__(self, value=None) -> None:
        self.value = value

    def one_or_none(self):
        """Return the configured optional row."""
        return self.value

    def one(self):
        """Return the configured required row."""
        return self.value

    def scalar_one_or_none(self):
        """Return the configured optional scalar."""
        return self.value

    def scalar_one(self):
        """Return the configured required scalar."""
        return self.value

    def mappings(self):
        """Keep mapping-result chaining on this fake."""
        return self

    def scalars(self):
        """Keep scalar-result chaining on this fake."""
        return self

    def all(self):
        """Return a configured row collection."""
        return self.value or []


class RecordingConnection:
    """Records SQL and returns results in a deterministic order."""

    def __init__(self, responses=()) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, statement, parameters=None):
        """Record one statement and return the next configured result."""
        self.calls.append((str(statement), parameters))
        return FakeResult(self.responses.popleft() if self.responses else None)


class RecordingEngine:
    """Provides transaction contexts backed by one recording connection."""

    def __init__(self, responses=()) -> None:
        self.connection = RecordingConnection(responses)

    @contextmanager
    def begin(self):
        """Yield the recording connection as a transaction."""
        yield self.connection


class FakeVectorStore:
    """Returns configured vector points and records query arguments."""

    def __init__(self, points=()) -> None:
        self.points = list(points)
        self.calls: list[dict] = []

    def query(self, **kwargs):
        """Return configured candidates for one retrieval request."""
        self.calls.append(kwargs)
        return self.points


def build_domain(*, engine=None, vector_store=None, provider=None, web_search=None):
    """Create a workflow domain with deterministic local collaborators."""
    return SqlEvidenceWorkflowDomain(
        engine=engine or RecordingEngine(),
        provider=provider or SimpleNamespace(model="model-a"),
        vector_store=vector_store or FakeVectorStore(),
        pipeline_version="pipeline-v1",
        web_search=web_search,
    )


def base_state(**overrides):
    """Build the minimum state shared by workflow unit tests."""
    state = {
        "run_id": str(RUN_ID),
        "user_id": str(USER_ID),
        "project_id": str(PROJECT_ID),
        "research_goal": "Compare the available evidence.",
        "review_policy": "strict",
        "run_kind": "evidence_review",
        "selected_document_ids": [],
        "allow_web": False,
        "retrieval_limit": 12,
        "claims": [],
        "relations": [],
        "evidence_batches": [],
    }
    state.update(overrides)
    return state


def claim(*, text="Supported claim", confidence=0.9, chunk_ids=None):
    """Build a serialized claim with stable evidence identifiers."""
    return {
        "text": text,
        "stance": "supports",
        "confidence": confidence,
        "evidence_ids": [1],
        "chunk_ids": chunk_ids or [str(CHUNK_ID)],
        "question_index": 0,
    }


def test_pipeline_configuration_and_runtime_error_preserve_contracts() -> None:
    """Validate pipeline bounds and retryable domain errors."""
    config = WorkflowPipelineConfig(
        retrieval_limit=50,
        model="model-a",
        evidence_prompt_version="evidence-review-v1",
    )
    error = WorkflowRuntimeError("WEB_SEARCH_UNAVAILABLE", retryable=True)

    assert config.retrieval_limit == 50
    assert error.code == "WEB_SEARCH_UNAVAILABLE"
    assert error.retryable is True
    with pytest.raises(ValueError):
        WorkflowPipelineConfig(
            retrieval_limit=0,
            model="model-a",
            evidence_prompt_version="evidence-review-v1",
        )


def test_bind_run_calls_provider_hook_when_available() -> None:
    """Bind budget and telemetry providers to the active run when supported."""
    provider = SimpleNamespace(calls=[], bind_run=lambda value: provider.calls.append(value))
    domain = build_domain(provider=provider)

    domain.bind_run(RUN_ID)

    assert provider.calls == [RUN_ID]


def test_plan_uses_provider_for_new_runs_and_exact_sections_for_refresh(monkeypatch) -> None:
    """Plan normal research through the provider and refreshes through selected sections."""
    domain = build_domain()
    events: list[tuple] = []
    monkeypatch.setattr(domain, "_node_started", lambda *args: events.append(args))
    monkeypatch.setattr(domain, "_node_completed", lambda *args: events.append(args))
    monkeypatch.setattr(
        workflow_runtime,
        "build_research_plan",
        lambda _provider, goal: ResearchPlan(questions=[f"{goal} A", f"{goal} B"]),
    )

    regular = domain.plan(base_state())
    refresh = domain.plan(
        base_state(run_kind="report_refresh", impacted_section_keys=["risk", "summary"])
    )

    assert regular["questions"] == [
        "Compare the available evidence. A",
        "Compare the available evidence. B",
    ]
    assert refresh["questions"] == [
        "Re-evaluate evidence that can change report section 'risk'.",
        "Re-evaluate evidence that can change report section 'summary'.",
    ]
    assert len(events) == 4


def test_retrieve_extracts_claims_from_owned_chunks(monkeypatch) -> None:
    """Map vector candidates to owned chunks and server-controlled claim evidence."""
    vector_store = FakeVectorStore(
        [
            {"payload": {"chunk_id": str(CHUNK_ID)}},
            {"payload": {"chunk_id": "not-a-uuid"}},
        ]
    )
    domain = build_domain(vector_store=vector_store)
    chunk = ChunkEntry(
        id=CHUNK_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=UUID("00000000-0000-4000-8000-000000000105"),
        source_type=SourceType.LOCAL_DOC,
        source_title="Study",
        text="Measured result.",
        page_no=3,
    )
    monkeypatch.setattr(domain, "_load_chunks", lambda *_args: [chunk])
    monkeypatch.setattr(domain, "_node_started", lambda *_args: None)
    monkeypatch.setattr(domain, "_node_completed", lambda *_args: None)
    monkeypatch.setattr(
        workflow_runtime,
        "extract_claims",
        lambda *_args: ClaimBatch(
            claims=[
                ExtractedClaim(
                    text="Measured result",
                    stance="supports",
                    confidence=0.9,
                    evidence_ids=[1],
                )
            ]
        ),
    )

    result = domain.retrieve_and_extract(
        base_state(question="What was measured?", question_index=0)
    )

    batch = result["evidence_batches"][0]
    assert batch["chunks"][0]["page_no"] == 3
    assert batch["claims"][0]["chunk_ids"] == [str(CHUNK_ID)]
    assert vector_store.calls[0]["document_ids"] is None


def test_retrieve_fails_closed_for_missing_evidence_or_web_provider(monkeypatch) -> None:
    """Expose explicit errors instead of synthesizing without evidence or configuration."""
    domain = build_domain()
    monkeypatch.setattr(domain, "_node_started", lambda *_args: None)
    monkeypatch.setattr(domain, "_load_chunks", lambda *_args: [])

    with pytest.raises(WorkflowRuntimeError, match="EVIDENCE_NOT_FOUND"):
        domain.retrieve_and_extract(base_state(question="Missing?", question_index=0))

    with pytest.raises(WorkflowRuntimeError, match="WEB_SEARCH_NOT_CONFIGURED"):
        domain.retrieve_and_extract(
            base_state(question="Search?", question_index=0, allow_web=True)
        )


