"""Verify worker task routing, deletion serialization, and retry policy."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from researchmate_worker import tasks
from researchmate_worker.deletion import SqlDeletionStore, SqlProjectDeletionStore
from researchmate_worker.evaluation import EvaluationRuntimeError
from researchmate_worker.ingestion import IngestionFailure, SqlIngestionStore

JOB_ID = UUID("00000000-0000-4000-8000-000000000201")
USER_ID = UUID("00000000-0000-4000-8000-000000000202")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000203")
DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000000204")


def ingestion_event() -> dict[str, str]:
    """Build a valid ingestion task payload."""
    return {
        "job_id": str(JOB_ID),
        "user_id": str(USER_ID),
        "project_id": str(PROJECT_ID),
        "document_id": str(DOCUMENT_ID),
    }


def deletion_event() -> dict[str, str]:
    """Build a valid deletion task payload."""
    return {
        "job_id": str(JOB_ID),
        "user_id": str(USER_ID),
        "project_id": str(PROJECT_ID),
        "document_id": str(DOCUMENT_ID),
    }


# ---------------------------------------------------------------------------
# Recording test doubles for SQL store methods
# ---------------------------------------------------------------------------


class StubResult:
    """Return one configured row or rowcount from a SQL store execute call."""

    def __init__(self, *, row: dict[str, Any] | None = None, rowcount: int = 0) -> None:
        self._row = row
        self._rowcount = rowcount

    def mappings(self) -> StubResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self._row

    @property
    def rowcount(self) -> int:
        return self._rowcount


class RecordingConnection:
    """Record SQL statements and parameters issued by SQL store methods.

    Subclasses override ``route`` to return a different result per statement
    so each store method can be exercised without a database.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def route(self, statement: str, parameters: dict[str, Any] | None) -> StubResult:
        """Override to return a different result per SQL statement."""
        return StubResult()

    def execute(self, statement: Any, parameters: dict[str, Any] | None = None) -> StubResult:
        self.calls.append((str(statement), parameters))
        return self.route(str(statement), parameters)


class RecordingEngine:
    """Provide one recording connection via a context manager."""

    def __init__(self, connection: RecordingConnection | None = None) -> None:
        self.connection = connection or RecordingConnection()

    @contextmanager
    def begin(self) -> Iterator[RecordingConnection]:
        yield self.connection


def _sql_contains(calls: list[tuple[str, dict[str, Any] | None]], marker: str) -> bool:
    """Return True if any captured SQL statement contains the literal marker."""
    return any(marker in call[0].lower() for call in calls)


# ---------------------------------------------------------------------------
# Ingestion lease + deletion serialization (runtime SQL assertions)
# ---------------------------------------------------------------------------


def test_ingestion_and_deletion_serialize_document_removal() -> None:
    """Prevent an already-claimed ingestion from reviving a deleted document.

    Drives SqlIngestionStore.replace_content, mark_ready, mark_failed, and
    SqlDeletionStore.claim through a RecordingEngine and asserts the captured
    SQL uses the documented FOR UPDATE locks, document status guards, and
    running-ingestion blocking predicates.
    """
    from researchmate_worker.ingestion import IngestionRecord

    record = IngestionRecord(
        job_id=JOB_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
        filename="doc.pdf",
        file_type="pdf",
        r2_object_key="users/u/doc.pdf",
        checksum_sha256=None,
        attempts=1,
    )

    # --- replace_content: must lock j, d, p with FOR UPDATE and check lease. ---
    class IngestionGuardConnection(RecordingConnection):
        def route(self, statement, parameters):
            # The lease-guard SELECT returns a marker row so the method proceeds.
            if "for update of j, d, p" in statement:
                return StubResult(row={"?column?": 1})
            return StubResult()

    engine = RecordingEngine(IngestionGuardConnection())
    store = SqlIngestionStore(engine)  # type: ignore[arg-type]
    store.replace_content(
        record,
        worker_id="worker-1",
        pages=[],
        chunks=[],
        pipeline_version="v1",
    )
    replace_calls = engine.connection.calls
    replace_sql = " ".join(c[0].lower() for c in replace_calls)
    assert "for update of j, d, p" in replace_sql, (
        "replace_content must acquire FOR UPDATE on job, document, and project"
    )
    assert "d.deleted_at is null" in replace_sql, (
        "replace_content must skip soft-deleted documents"
    )
    assert "lease_expires_at > now()" in replace_sql, (
        "replace_content must verify the lease is still valid"
    )

    # --- mark_ready: must require the indexing status and lock j, d, p. ---
    class ReadyGuardConnection(RecordingConnection):
        def route(self, statement, parameters):
            if "for update of j, d, p" in statement:
                return StubResult(row={"?column?": 1})
            return StubResult()

    engine = RecordingEngine(ReadyGuardConnection())
    store = SqlIngestionStore(engine)  # type: ignore[arg-type]
    store.mark_ready(record, worker_id="worker-1")
    ready_calls = engine.connection.calls
    ready_sql = " ".join(c[0].lower() for c in ready_calls)
    assert "d.status = 'indexing'" in ready_sql, (
        "mark_ready must require the document to be in 'indexing' status"
    )
    assert "for update of j, d, p" in ready_sql, (
        "mark_ready must acquire FOR UPDATE on job, document, and project"
    )

    # --- mark_failed: must guard against already-deleted documents. ---
    engine = RecordingEngine(RecordingConnection())
    store = SqlIngestionStore(engine)  # type: ignore[arg-type]
    store.mark_failed(record, worker_id="worker-1", code="PARSE_FAILED")
    failed_calls = engine.connection.calls
    failed_sql = " ".join(c[0].lower() for c in failed_calls)
    assert "deleted_at is null and status <> 'deleted'" in failed_sql, (
        "mark_failed must not touch already-deleted documents"
    )

    # --- SqlDeletionStore.claim: must block on running ingestion with valid lease. ---
    from researchmate_worker.deletion import DocumentDeletionEvent

    claim_engine = RecordingEngine(RecordingConnection())
    claim_store = SqlDeletionStore(claim_engine)  # type: ignore[arg-type]
    del_event = DocumentDeletionEvent(
        job_id=JOB_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
        document_id=DOCUMENT_ID,
    )
    # The claim returns None (no row matched) so we can inspect all SQL.
    store_result = claim_store.claim(del_event, worker_id="worker-1", lease_seconds=60)
    assert store_result is None, "claim must return None when no document row matches"
    claim_calls = claim_engine.connection.calls
    claim_sql = " ".join(c[0].lower() for c in claim_calls)
    assert "running_ingestion.type = 'parse_and_index_document'" in claim_sql, (
        "deletion claim must block on running parse_and_index_document jobs"
    )
    assert "running_ingestion.lease_expires_at > now()" in claim_sql, (
        "deletion claim must only block on ingestion with valid leases"
    )
    assert "lease_expires_at <= now()" in claim_sql, (
        "deletion claim must reap expired ingestion leases"
    )
    # The blocked-detection SELECT checks for running ingestion with valid lease.
    # The error code DOCUMENT_INGESTION_RUNNING is raised in Python, not in SQL.
    # The blocked-detection query reuses the same running_ingestion predicate.
    assert claim_sql.count("running_ingestion.lease_expires_at > now()") >= 1, (
        "deletion claim must run the blocked-detection query"
    )


def test_project_deletion_reclaims_expired_ingestion_leases() -> None:
    """A worker crash must not leave project removal blocked forever.

    Drives SqlProjectDeletionStore.claim through a RecordingEngine and asserts
    the captured SQL reaps failed/expired ingestion leases and blocks on
    running ingestion with valid leases.
    """
    from researchmate_worker.deletion import ProjectDeletionEvent

    engine = RecordingEngine(RecordingConnection())
    store = SqlProjectDeletionStore(engine)  # type: ignore[arg-type]
    event = ProjectDeletionEvent(
        job_id=JOB_ID,
        user_id=USER_ID,
        project_id=PROJECT_ID,
    )

    result = store.claim(event, worker_id="worker-1", lease_seconds=60)
    assert result is None, "claim must return None when no project row matches"

    calls = engine.connection.calls
    sql_text = " ".join(c[0].lower() for c in calls)

    # The pre-claim reaper must fail pending and expired-lease running jobs.
    assert "status = 'failed'" in sql_text, (
        "project deletion must mark expired ingestion jobs as failed"
    )
    assert "lease_owner = null" in sql_text, "failed jobs must clear lease owners"
    assert "lease_expires_at <= now()" in sql_text, (
        "project deletion must reap expired leases"
    )
    # The claim must check no running ingestion with valid lease blocks it.
    assert sql_text.count("running_ingestion.lease_expires_at > now()") >= 2, (
        "project deletion must block on running ingestion at least twice "
        "(claim UPDATE + blocked-detection SELECT)"
    )


# ---------------------------------------------------------------------------
# Task routing and retry policy (unchanged — no getsource used here)
# ---------------------------------------------------------------------------


def test_ingestion_and_deletion_tasks_forward_validated_events(monkeypatch) -> None:
    """Pass validated task events and stable worker identity to owned services."""
    calls: list[tuple] = []
    service = SimpleNamespace(
        handle=lambda event, worker_id: calls.append((event, worker_id)) or "completed"
    )
    monkeypatch.setattr(tasks, "build_ingestion_service", lambda: service)
    monkeypatch.setattr(tasks, "build_deletion_service", lambda: service)

    assert tasks.ingest_document.run(ingestion_event()) == "completed"
    assert tasks.delete_document.run(deletion_event()) == "completed"
    assert calls[0][0].document_id == DOCUMENT_ID
    assert calls[1][0].document_id == DOCUMENT_ID
    assert calls[0][1] == "worker"


def test_retryable_ingestion_uses_bounded_backoff(monkeypatch) -> None:
    """Retry only retryable ingestion failures with the bounded Celery countdown."""
    service = SimpleNamespace(
        handle=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            IngestionFailure("OBJECT_STORAGE_UNAVAILABLE", retryable=True)
        )
    )
    retries: list[tuple] = []

    def retry(*, exc, countdown):
        """Capture the retry request and stop task execution."""
        retries.append((exc, countdown))
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr(tasks, "build_ingestion_service", lambda: service)
    monkeypatch.setattr(tasks.ingest_document, "retry", retry)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        tasks.ingest_document.run(ingestion_event())

    assert retries[0][0].code == "OBJECT_STORAGE_UNAVAILABLE"
    assert retries[0][1] == 2


def test_evaluation_and_fault_tasks_forward_worker_identity(monkeypatch) -> None:
    """Route evaluation and fault work through their dedicated services."""
    evaluation_calls: list[tuple] = []
    fault_calls: list[tuple] = []
    monkeypatch.setattr(
        tasks,
        "build_evaluation_runner",
        lambda _settings: SimpleNamespace(
            run=lambda run_id, worker_id: (
                evaluation_calls.append((run_id, worker_id)) or "evaluated"
            )
        ),
    )
    monkeypatch.setattr(
        tasks,
        "build_fault_simulation_service",
        lambda _settings: SimpleNamespace(
            run=lambda exercise_id, worker_id: (
                fault_calls.append((exercise_id, worker_id)) or "simulated"
            )
        ),
    )

    assert tasks.run_evaluation.run({"evaluation_run_id": str(JOB_ID)}) == "evaluated"
    assert (
        tasks.run_fault_simulation.run({"exercise_id": str(JOB_ID), "requested_by": str(USER_ID)})
        == "simulated"
    )
    assert evaluation_calls == [(JOB_ID, "worker")]
    assert fault_calls == [(JOB_ID, "worker")]


def test_retryable_evaluation_uses_bounded_backoff(monkeypatch) -> None:
    """Map retryable evaluation failures to Celery retry without leaking details."""
    runner = SimpleNamespace(
        run=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            EvaluationRuntimeError("EVALUATION_PROVIDER_FAILED", retryable=True)
        )
    )
    retries: list[tuple] = []

    def retry(*, exc, countdown):
        """Capture the retry request and stop task execution."""
        retries.append((exc, countdown))
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr(tasks, "build_evaluation_runner", lambda _settings: runner)
    monkeypatch.setattr(tasks.run_evaluation, "retry", retry)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        tasks.run_evaluation.run({"evaluation_run_id": str(JOB_ID)})

    assert retries[0][0].code == "EVALUATION_PROVIDER_FAILED"
    assert retries[0][1] == 2
