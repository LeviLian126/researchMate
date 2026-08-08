"""Verify PostgreSQL evidence-repository behavior with isolated unit doubles."""

# Verifies evidence-repository mapping and ownership contracts without emulating PostgreSQL.
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from inspect import getsource
from typing import Any
from uuid import UUID

from researchmate_api.persistence.evidence_postgres import (
    PostgresEvidenceRepository,
    _progress,
)
from researchmate_api.schemas.common import CurrentUser

RUN_ID = UUID("00000000-0000-4000-8000-000000000301")
USER_ID = UUID("00000000-0000-4000-8000-000000000302")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000303")
PIPELINE_ID = UUID("00000000-0000-4000-8000-000000000304")
NOW = datetime(2026, 7, 26, tzinfo=UTC)


class SequentialResult:
    """Exposes mapping, scalar, and row access over one configured value."""

    def __init__(self, value: Any = None) -> None:  # boundary: opaque test double
        self.value = value

    def mappings(self) -> SequentialResult:
        """Keep mapping access on this result."""
        return self

    def one_or_none(self) -> Any:  # boundary: opaque test double
        """Return one optional row."""
        return self.value

    def scalar_one(self) -> Any:  # boundary: opaque test double
        """Return one required scalar."""
        return self.value

    def all(self) -> list[Any]:
        """Return a configured row collection."""
        return self.value or []


class SequentialConnection:
    """Records SQL and returns values in call order."""

    def __init__(self, values: Any = ()) -> None:  # boundary: opaque test double
        self.values = deque(values)
        self.calls: list[tuple[str, dict | None]] = []

    # statement is an opaque SQLAlchemy expression; parameters is a bound-parameter mapping.
    def execute(
        self, statement: Any, parameters: dict[str, Any] | None = None
    ) -> SequentialResult:  # boundary: opaque test double
        """Record one statement and return the next configured value."""
        self.calls.append((str(statement), parameters))
        return SequentialResult(self.values.popleft() if self.values else None)


class SequentialEngine:
    """Provides a transaction around one sequential connection."""

    def __init__(self, values: Any = ()) -> None:  # boundary: opaque test double
        self.connection = SequentialConnection(values)

    @contextmanager
    def begin(self) -> Any:  # boundary: opaque test double
        """Yield the configured connection."""
        yield self.connection


def test_progress_uses_safe_payload_and_clamps_untrusted_values() -> None:
    """Map durable status to bounded user-visible progress."""
    assert _progress("running", None) == 25
    assert _progress("waiting_human", None) == 65
    assert _progress("succeeded", None) == 100
    assert _progress("unknown", None) == 0
    assert _progress("running", {"progress": -20}) == 0
    assert _progress("running", {"progress": 150}) == 100
    assert _progress("running", {"progress": 47}) == 47
    assert _progress("running", {"progress": "47"}) == 25


def test_get_run_sets_owner_context_and_maps_review_state() -> None:
    """Enforce the owner predicate and expose bounded workflow state."""
    row = {
        "id": RUN_ID,
        "project_id": PROJECT_ID,
        "pipeline_version_id": PIPELINE_ID,
        "kind": "evidence_review",
        "status": "waiting_human",
        "output": None,
        "error_code": None,
        "created_at": NOW,
        "started_at": NOW,
        "completed_at": None,
        "current_node": "human_review",
        "safe_payload": {"progress": 61},
    }
    engine = SequentialEngine([None, row])
    repository = PostgresEvidenceRepository(engine)  # type: ignore[arg-type]
    user = CurrentUser(id=USER_ID)

    result = repository.get_run(user, RUN_ID)

    assert result is not None
    assert result.run_id == RUN_ID
    assert result.progress == 61
    assert result.review_required is True
    assert result.current_node == "human_review"
    assert "set_config('request.jwt.claim.sub'" in engine.connection.calls[0][0]
    lookup_sql, lookup_params = engine.connection.calls[1]
    assert "r.user_id = :user_id" in lookup_sql
    assert lookup_params == {"run_id": RUN_ID, "user_id": USER_ID}


def test_get_run_returns_none_for_concealed_resource() -> None:
    """Conceal absent or foreign runs rather than constructing a partial record."""
    repository = PostgresEvidenceRepository(
        SequentialEngine([None, None])  # type: ignore[arg-type]
    )

    assert repository.get_run(CurrentUser(id=USER_ID), RUN_ID) is None


def test_list_events_requires_ownership_and_preserves_sequence() -> None:
    """Return ordered safe events only after the run ownership check."""
    rows = [
        {
            "event_id": 7,
            "sequence": 2,
            "node_key": "reconcile",
            "event_type": "node_completed",
            "attempt": 1,
            "status": "succeeded",
            "safe_payload": {"progress": 60},
            "latency_ms": 12,
            "created_at": NOW,
        }
    ]
    engine = SequentialEngine([None, 1, rows])
    repository = PostgresEvidenceRepository(engine)  # type: ignore[arg-type]

    events = repository.list_run_events(CurrentUser(id=USER_ID), RUN_ID, 1)

    assert events is not None
    assert [(event.sequence, event.node_key) for event in events] == [(2, "reconcile")]
    event_sql, event_params = engine.connection.calls[2]
    assert "sequence > :after_sequence" in event_sql
    assert event_params == {"run_id": RUN_ID, "after_sequence": 1}

    concealed = PostgresEvidenceRepository(
        SequentialEngine([None, None])  # type: ignore[arg-type]
    )
    assert concealed.list_run_events(CurrentUser(id=USER_ID), RUN_ID, 0) is None


def test_accepted_responses_use_stable_resource_urls() -> None:
    """Build accepted command responses from server-owned identifiers."""
    accepted = PostgresEvidenceRepository._accepted_run(RUN_ID, NOW)
    decision = PostgresEvidenceRepository._accepted_decision(UUID(int=400), RUN_ID)

    assert accepted.status_url == f"/api/v1/runs/{RUN_ID}"
    assert accepted.events_url == f"/api/v1/runs/{RUN_ID}/events"
    assert decision.resume_status_url == f"/api/v1/runs/{RUN_ID}"


def test_refresh_acceptance_uses_persisted_or_fallback_sections() -> None:
    """Prefer persisted impact analysis and retain a deterministic fallback."""
    persisted_connection = SequentialConnection([{"impacted_section_keys": ["risk", "summary"]}])
    fallback_connection = SequentialConnection([{}])

    persisted = PostgresEvidenceRepository._refresh_accepted(
        persisted_connection,  # type: ignore[arg-type]
        RUN_ID,
        UUID(int=401),
        3,
        ["fallback"],
    )
    fallback = PostgresEvidenceRepository._refresh_accepted(
        fallback_connection,  # type: ignore[arg-type]
        RUN_ID,
        UUID(int=401),
        3,
        ["fallback"],
    )

    assert persisted.impacted_section_keys == ["risk", "summary"]
    assert fallback.impacted_section_keys == ["fallback"]
    assert persisted.base_revision == 3
    assert persisted.planned_revision == 4


def test_evidence_writes_require_active_projects_without_rejecting_global_datasets() -> None:
    """Keep project-scoped writes closed while preserving project-less golden sets."""
    create_run = getsource(PostgresEvidenceRepository.create_research_run).lower()
    decide = getsource(PostgresEvidenceRepository.create_decision).lower()
    refresh = getsource(PostgresEvidenceRepository.refresh_report).lower()
    evaluate = getsource(PostgresEvidenceRepository.create_evaluation_run).lower()

    assert "p.status = 'active'" in create_run
    assert "p.status = 'active'" in decide
    assert "p.status = 'active'" in refresh
    assert "left join projects p" in evaluate
    assert "d.project_id is null" in evaluate
    assert "p.status = 'active'" in evaluate
