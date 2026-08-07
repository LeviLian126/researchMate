"""Verify worker heartbeat, dispatcher, and bootstrap failure boundaries."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from inspect import getsource
from types import SimpleNamespace
from uuid import UUID

import pytest
from researchmate_worker import dispatch_outbox, tasks
from researchmate_worker.runtime_health import record_heartbeat

JOB_ID = UUID("00000000-0000-4000-8000-000000000201")
USER_ID = UUID("00000000-0000-4000-8000-000000000202")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000203")


class RecordingConnection:
    """Records SQLAlchemy-style execute calls for boundary assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, statement, parameters=None):
        """Record one SQL statement and its safe parameters."""
        self.calls.append((str(statement), parameters))
        return SimpleNamespace()


class RecordingEngine:
    """Provides one transactional recording connection."""

    def __init__(self) -> None:
        self.connection = RecordingConnection()

    @contextmanager
    def begin(self):
        """Yield the recording connection."""
        yield self.connection


def ingestion_event() -> dict[str, str]:
    """Build the minimum valid ingestion payload for bootstrap recovery tests."""
    return {
        "job_id": str(JOB_ID),
        "user_id": "00000000-0000-4000-8000-000000000202",
        "project_id": "00000000-0000-4000-8000-000000000203",
        "document_id": "00000000-0000-4000-8000-000000000204",
    }


def test_runtime_heartbeat_writes_bounded_metadata(monkeypatch) -> None:
    """Upsert a safe heartbeat with an explicit or host-derived instance ID."""
    engine = RecordingEngine()
    monkeypatch.setattr("researchmate_worker.runtime_health.socket.gethostname", lambda: "worker-a")

    record_heartbeat(engine, "worker", metadata={"queue": "ingestion"})

    sql, parameters = engine.connection.calls[0]
    assert "on conflict (component) do update" in sql
    assert parameters == {
        "component": "worker",
        "instance_id": "worker-a",
        "status": "ready",
        "metadata": '{"queue":"ingestion"}',
    }


def test_build_dispatcher_requires_database_and_uses_configured_limits(monkeypatch) -> None:
    """Fail closed without durable state and pass configured queue limits to the dispatcher."""
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        dispatch_outbox.build_dispatcher(SimpleNamespace(database_url=None))

    engine = object()
    store = SimpleNamespace(name="store")
    publisher = SimpleNamespace(name="publisher")
    captured = {}
    monkeypatch.setattr(dispatch_outbox, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        dispatch_outbox, "SqlOutboxStore", lambda value: store if value is engine else None
    )
    monkeypatch.setattr(
        dispatch_outbox,
        "CeleryTaskPublisher",
        lambda app, queue: (
            publisher if app is dispatch_outbox.celery_app and queue == "ingestion" else None
        ),
    )

    def build(store_value, publisher_value, **kwargs):
        """Capture dispatcher dependencies and limits."""
        captured.update(store=store_value, publisher=publisher_value, **kwargs)
        return "dispatcher"

    monkeypatch.setattr(dispatch_outbox, "OutboxDispatcher", build)
    settings = SimpleNamespace(
        database_url="postgresql+psycopg://db",
        ingestion_queue="ingestion",
        outbox_batch_size=20,
        outbox_max_attempts=7,
    )

    assert dispatch_outbox.build_dispatcher(settings) == "dispatcher"
    assert captured == {
        "store": store,
        "publisher": publisher,
        "batch_size": 20,
        "max_attempts": 7,
    }


def test_dispatcher_once_records_heartbeat_and_exits(monkeypatch) -> None:
    """Exercise one bounded dispatcher poll without sleeping."""
    engine = object()
    fake_dispatcher = SimpleNamespace(
        store=SimpleNamespace(engine=engine),
        recover_stale_claims=lambda: None,
        dispatch_once=lambda: 2,
    )
    heartbeats: list[tuple] = []
    monkeypatch.setattr(sys, "argv", ["dispatch_outbox", "--once", "--poll-seconds", "0"])
    monkeypatch.setattr(
        dispatch_outbox,
        "WorkerSettings",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(dispatch_outbox, "build_dispatcher", lambda _settings: fake_dispatcher)
    monkeypatch.setattr(
        dispatch_outbox,
        "record_heartbeat",
        lambda *args, **kwargs: heartbeats.append((args, kwargs)),
    )

    dispatch_outbox.main()

    assert heartbeats == [((engine, "dispatcher"), {"metadata": {"poll_seconds": 0.25}})]


def test_task_builders_fail_closed_without_managed_configuration(monkeypatch) -> None:
    """Reject managed worker construction when required providers are absent."""
    empty = SimpleNamespace(
        database_url=None,
        object_storage_configured=False,
        embedding_provider="fake",
        nvidia_api_key=None,
        qdrant_url=None,
        llm_provider="fake",
    )
    monkeypatch.setattr(tasks, "WorkerSettings", lambda: empty)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        tasks.build_ingestion_service()
    with pytest.raises(RuntimeError, match="Database, S3-compatible"):
        tasks.build_deletion_service()
    with pytest.raises(RuntimeError, match="Database and Qdrant"):
        tasks.build_workflow_domain(empty)
    with pytest.raises(RuntimeError, match="Database, Qdrant, and NVIDIA"):
        tasks.build_evaluation_runner(empty)
    with pytest.raises(RuntimeError, match="Database is required"):
        tasks.build_fault_simulation_service(empty)


def test_bootstrap_failure_update_is_bounded_and_optional(monkeypatch) -> None:
    """Skip absent databases and write a bounded terminal error when configured."""
    tasks._mark_workflow_bootstrap_failed(SimpleNamespace(database_url=None), JOB_ID, "ignored")
    engine = RecordingEngine()
    monkeypatch.setattr(tasks, "create_engine", lambda *_args, **_kwargs: engine)

    tasks._mark_workflow_bootstrap_failed(
        SimpleNamespace(database_url="postgresql+psycopg://db"),
        JOB_ID,
        "X" * 200,
    )

    sql, parameters = engine.connection.calls[0]
    assert "status='failed'" in sql
    assert parameters["run_id"] == JOB_ID
    assert len(parameters["code"]) == 120


def test_job_bootstrap_failure_does_not_overwrite_an_active_worker_lease() -> None:
    """Only fail pending or expired jobs when construction fails before claim."""
    source = getsource(tasks._mark_job_bootstrap_failed).lower()
    job_update = source.split("returning type", 1)[0]

    assert "status='pending'" in job_update
    assert "lease_expires_at < now()" in job_update
    assert "status in ('pending','running')" not in job_update


def test_task_bootstrap_failure_marks_job_terminal(monkeypatch) -> None:
    """Surface construction failures instead of leaving a published job pending forever."""
    marked: list[tuple] = []
    monkeypatch.setattr(tasks, "WorkerSettings", lambda: SimpleNamespace(database_url=None))
    monkeypatch.setattr(
        tasks,
        "build_project_deletion_service",
        lambda: (_ for _ in ()).throw(AttributeError("config drift")),
    )
    monkeypatch.setattr(
        tasks,
        "_mark_job_bootstrap_failed",
        lambda settings, job_id, code: marked.append((settings, job_id, code)),
    )

    event = {
        "job_id": str(JOB_ID),
        "user_id": str(USER_ID),
        "project_id": str(PROJECT_ID),
    }
    with pytest.raises(AttributeError, match="config drift"):
        tasks.delete_project.run(event)

    assert marked[0][1:] == (JOB_ID, "PROJECT_DELETION_BOOTSTRAP_FAILED")


def test_invalid_worker_settings_still_mark_the_published_job(monkeypatch) -> None:
    """Keep configuration parsing inside the bootstrap recovery boundary."""
    marked: list[tuple] = []
    monkeypatch.setattr(
        tasks,
        "WorkerSettings",
        lambda: (_ for _ in ()).throw(ValueError("invalid worker config")),
    )
    monkeypatch.setattr(
        tasks,
        "_mark_job_bootstrap_failed",
        lambda settings, job_id, code: marked.append((settings, job_id, code)),
    )

    with pytest.raises(ValueError, match="invalid worker config"):
        tasks.ingest_document.run(ingestion_event())

    assert marked == [(None, JOB_ID, "WORKER_CONFIG_INVALID")]
