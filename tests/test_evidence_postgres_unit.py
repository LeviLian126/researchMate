"""Verify PostgreSQL evidence-repository behavior with isolated unit doubles."""

# Verifies evidence-repository mapping and ownership contracts without emulating PostgreSQL.
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
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

    def scalars(self) -> SequentialResult:
        """Keep scalar access on this result."""
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

    def __iter__(self) -> Any:
        """Iterate mapping results; expose rows when configured."""
        return iter(self.value if isinstance(self.value, list) else [])


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
    """Build accepted command responses from server-owned identifiers.

    Observes the URL construction through create_research_run (fresh-insert path)
    and create_decision (fresh-insert path). Both methods call their respective
    static accepted-response builders as the final step before returning.
    """
    from researchmate_api.schemas.evidence import (
        HumanDecisionCreate,
        ResearchRunCreate,
    )

    PROJECT_ROW = {
        "id": RUN_ID,
        "project_id": PROJECT_ID,
        "pipeline_version_id": PIPELINE_ID,
        "kind": "evidence_review",
        "status": "pending",
        "output": None,
        "error_code": None,
        "created_at": NOW,
        "started_at": None,
        "completed_at": None,
        "current_node": None,
        "safe_payload": None,
    }
    # create_research_run values (in order):
    # RLS guard, advisory lock, idempotency check (None for fresh insert),
    # project lock, pipeline acceptance, document readiness, insert, event, outbox
    run_engine = SequentialEngine([None, None, None, 1, 1, 1, PROJECT_ROW, None, None])
    run_repo = PostgresEvidenceRepository(run_engine)  # type: ignore[arg-type]
    run_result = run_repo.create_research_run(
        CurrentUser(id=USER_ID),
        ResearchRunCreate(
            project_id=PROJECT_ID,
            pipeline_version_id=PIPELINE_ID,
            research_goal="x" * 20,
            max_cost_usd=None,
        ),
        idempotency_key="key-1",
    )

    assert run_result is not None
    assert run_result.status_url == f"/api/v1/runs/{run_result.run_id}"
    assert run_result.events_url == f"/api/v1/runs/{run_result.run_id}/events"

    # create_decision values (in order):
    # RLS guard, advisory lock, run+project lock, idempotency check (None),
    # proposed event lookup, insert human_decisions, update workflow_runs,
    # append event, append outbox
    decision_engine = SequentialEngine([
        None,  # RLS guard
        None,  # advisory lock
        {"id": RUN_ID, "status": "waiting_human"},  # run+project lock
        None,  # idempotency check
        {"id": UUID(int=7), "safe_payload": {"interrupt_key": "k1"}},  # proposed event
        None,  # insert human_decisions
        None,  # update workflow_runs
        None,  # append event
        None,  # append outbox
    ])
    decision_repo = PostgresEvidenceRepository(decision_engine)  # type: ignore[arg-type]
    decision_result = decision_repo.create_decision(
        CurrentUser(id=USER_ID),
        RUN_ID,
        HumanDecisionCreate(
            interrupt_key="k1",
            decision="approve",
        ),
        idempotency_key="dec-1",
    )

    assert decision_result is not None
    assert decision_result.resume_status_url == f"/api/v1/runs/{RUN_ID}"


def test_refresh_acceptance_uses_persisted_or_fallback_sections() -> None:
    """Prefer persisted impact analysis and retain a deterministic fallback.

    The idempotent-replay path of refresh_report requires the stored
    evidence_fingerprint hash to match the new payload, which is infeasible
    to construct in a unit test double. _refresh_accepted is the static helper
    that reads the stored input to recover impacted_section_keys or falls back.
    # testing private method: no public API exposes this behavior without a matching request hash
    """
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
    """Keep project-scoped writes closed while preserving project-less golden sets.

    Drives create_research_run, create_decision, refresh_report, and
    create_evaluation_run through RecordingConnections and asserts the
    captured SQL enforces the active-project predicate on project-scoped writes
    while preserving the LEFT JOIN for global datasets.
    """
    from researchmate_api.schemas.evidence import (
        EvaluationRunCreate,
        HumanDecisionCreate,
        ReportRefreshCreate,
        ResearchRunCreate,
    )

    # --- create_research_run: must enforce p.status = 'active'. ---
    run_engine = SequentialEngine([None, None, None, 1, 1, 1, None, None, None])
    run_repo = PostgresEvidenceRepository(run_engine)  # type: ignore[arg-type]
    run_repo.create_research_run(
        CurrentUser(id=USER_ID),
        ResearchRunCreate(
            project_id=PROJECT_ID,
            pipeline_version_id=PIPELINE_ID,
            research_goal="x" * 20,
            max_cost_usd=None,
        ),
        idempotency_key="key-a",
    )
    create_run_sql = " ".join(
        call[0].lower() for call in run_engine.connection.calls
    )
    assert "p.status = 'active'" in create_run_sql, (
        "create_research_run must enforce the active-project predicate"
    )

    # --- create_decision: must enforce p.status = 'active'. ---
    decision_engine = SequentialEngine([
        None, None, {"id": RUN_ID, "status": "waiting_human"}, None,
        {"id": UUID(int=7), "safe_payload": {"interrupt_key": "k1"}}, None, None, None, None,
    ])
    decision_repo = PostgresEvidenceRepository(decision_engine)  # type: ignore[arg-type]
    decision_repo.create_decision(
        CurrentUser(id=USER_ID),
        RUN_ID,
        HumanDecisionCreate(
            interrupt_key="k1",
            decision="approve",
        ),
        idempotency_key="dec-a",
    )
    decide_sql = " ".join(
        call[0].lower() for call in decision_engine.connection.calls
    )
    assert "p.status = 'active'" in decide_sql, (
        "create_decision must enforce the active-project predicate"
    )

    # --- refresh_report: must enforce p.status = 'active'. ---
    refresh_engine = SequentialEngine([
        None, None, {"id": UUID(int=401), "project_id": PROJECT_ID, "revision": 3},
        None, 1, None, ["fallback"], None, None, None,
    ])
    refresh_repo = PostgresEvidenceRepository(refresh_engine)  # type: ignore[arg-type]
    refresh_repo.refresh_report(
        CurrentUser(id=USER_ID),
        UUID(int=401),
        ReportRefreshCreate(
            pipeline_version_id=PIPELINE_ID,
            force_sections=["fallback"],
        ),
        idempotency_key="key-b",
    )
    refresh_sql = " ".join(
        call[0].lower() for call in refresh_engine.connection.calls
    )
    assert "p.status = 'active'" in refresh_sql, (
        "refresh_report must enforce the active-project predicate"
    )

    # --- create_evaluation_run: must LEFT JOIN projects with global fallback. ---
    eval_engine = SequentialEngine([None, None, None, {"project_id": None, "dataset_user_id": USER_ID, "case_count": 1}, None, None])
    eval_repo = PostgresEvidenceRepository(eval_engine)  # type: ignore[arg-type]
    eval_repo.create_evaluation_run(
        CurrentUser(id=USER_ID),
        EvaluationRunCreate(
            dataset_id=UUID(int=305),
            pipeline_version_id=PIPELINE_ID,
            metrics=["schema_valid"],
            max_cost_usd=None,
        ),
        idempotency_key="eval-a",
    )
    eval_sql = " ".join(
        call[0].lower() for call in eval_engine.connection.calls
    )
    assert "left join projects p" in eval_sql, (
        "create_evaluation_run must LEFT JOIN projects for global datasets"
    )
    assert "d.project_id is null" in eval_sql, (
        "create_evaluation_run must preserve project-less golden datasets"
    )
    assert "p.status = 'active'" in eval_sql, (
        "create_evaluation_run must enforce the active-project predicate when project_id is present"
    )
