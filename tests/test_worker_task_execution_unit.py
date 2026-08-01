"""Verify worker task routing, deletion serialization, and retry policy."""
from __future__ import annotations

from inspect import getsource
from types import SimpleNamespace
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

def test_ingestion_and_deletion_serialize_document_removal() -> None:
    """Prevent an already-claimed ingestion from reviving a deleted document."""
    replace = getsource(SqlIngestionStore.replace_content).lower()
    ready = getsource(SqlIngestionStore.mark_ready).lower()
    failed = getsource(SqlIngestionStore.mark_failed).lower()
    delete_claim = getsource(SqlDeletionStore.claim).lower()

    assert "for update of j, d, p" in replace
    assert "d.deleted_at is null" in replace
    assert "d.status = 'indexing'" in ready
    assert "for update of j, d, p" in ready
    assert "deleted_at is null and status <> 'deleted'" in failed
    assert "running_ingestion.type = 'parse_and_index_document'" in delete_claim
    assert "running_ingestion.lease_expires_at > now()" in delete_claim
    assert "lease_expires_at <= now()" in delete_claim
    assert "document_ingestion_running" in delete_claim


def test_project_deletion_reclaims_expired_ingestion_leases() -> None:
    """A worker crash must not leave project removal blocked forever."""
    claim = getsource(SqlProjectDeletionStore.claim).lower()

    assert "status = 'failed'" in claim
    assert "lease_owner = null" in claim
    assert "lease_expires_at <= now()" in claim
    assert claim.count("running_ingestion.lease_expires_at > now()") >= 2
    assert "project_ingestion_running" in claim


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
            run=lambda run_id, worker_id: evaluation_calls.append((run_id, worker_id))
            or "evaluated"
        ),
    )
    monkeypatch.setattr(
        tasks,
        "build_fault_simulation_service",
        lambda _settings: SimpleNamespace(
            run=lambda exercise_id, worker_id: fault_calls.append((exercise_id, worker_id))
            or "simulated"
        ),
    )

    assert tasks.run_evaluation.run({"evaluation_run_id": str(JOB_ID)}) == "evaluated"
    assert (
        tasks.run_fault_simulation.run(
            {"exercise_id": str(JOB_ID), "requested_by": str(USER_ID)}
        )
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
