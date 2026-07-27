# Verifies worker entry points, parser failures, and heartbeat writes without external services.
from __future__ import annotations

import sys
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from researchmate_worker import dispatch_outbox, tasks
from researchmate_worker.evaluation import EvaluationRuntimeError
from researchmate_worker.ingestion import IngestionFailure, ParserAdapterError
from researchmate_worker.parsing import DoclingDocumentParser, _serialize_provenance
from researchmate_worker.runtime_health import record_heartbeat

JOB_ID = UUID("00000000-0000-4000-8000-000000000201")
USER_ID = UUID("00000000-0000-4000-8000-000000000202")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000203")
DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000000204")


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


def test_provenance_serialization_preserves_source_offsets() -> None:
    """Keep opaque source anchors and provide a structural fallback."""
    bbox = SimpleNamespace(model_dump=lambda **_kwargs: {"l": 1, "t": 2})
    item = SimpleNamespace(
        self_ref="#/texts/1",
        prov=[SimpleNamespace(page_no=4, bbox=bbox, charspan=(8, 14))],
    )
    no_anchor = SimpleNamespace(self_ref="#/texts/2", prov=[])

    assert _serialize_provenance(item, locator_kind="page") == [
        {
            "item_ref": "#/texts/1",
            "locator_kind": "page",
            "page_no": 4,
            "bbox": {"l": 1, "t": 2},
            "charspan": [8, 14],
        }
    ]
    assert _serialize_provenance(no_anchor, locator_kind="page")[0] == {
        "item_ref": "#/texts/2",
        "locator_kind": "structural",
        "page_no": None,
        "bbox": None,
        "charspan": None,
    }


def test_parser_rejects_unsupported_incomplete_and_failed_conversion(tmp_path) -> None:
    """Map parser boundary failures to stable non-secret error codes."""
    source = tmp_path / "source.bin"
    source.write_bytes(b"document")
    parser = DoclingDocumentParser(
        max_file_size=1024,
        max_num_pages=5,
        converter=SimpleNamespace(convert=lambda *_args, **_kwargs: None),
    )

    with pytest.raises(ParserAdapterError, match="UNSUPPORTED_DOCUMENT_TYPE"):
        parser.parse(source, file_type="txt")

    parser.converter = SimpleNamespace(
        convert=lambda *_args, **_kwargs: SimpleNamespace(
            status=SimpleNamespace(value="partial"),
            document=None,
        )
    )
    with pytest.raises(ParserAdapterError, match="PARSER_INCOMPLETE_RESULT"):
        parser.parse(source, file_type="pdf")

    def fail_conversion(*_args, **_kwargs):
        """Simulate an opaque converter failure."""
        raise OSError("private parser detail")

    parser.converter = SimpleNamespace(convert=fail_conversion)
    with pytest.raises(ParserAdapterError, match="PARSER_EXECUTION_FAILED"):
        parser.parse(source, file_type="pdf")


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
    monkeypatch.setattr(dispatch_outbox, "SqlOutboxStore", lambda value: store if value is engine else None)
    monkeypatch.setattr(
        dispatch_outbox,
        "CeleryTaskPublisher",
        lambda app, queue: publisher
        if app is dispatch_outbox.celery_app and queue == "ingestion"
        else None,
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

    assert heartbeats == [
        ((engine, "dispatcher"), {"metadata": {"poll_seconds": 0.25}})
    ]


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
