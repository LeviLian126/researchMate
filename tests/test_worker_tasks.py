from researchmate_worker.celery_app import celery_app
from researchmate_worker.ingestion import IngestionEvent


def test_celery_registers_ingestion_task_without_starting_external_services() -> None:
    import researchmate_worker.tasks  # noqa: F401

    assert "researchmate.ingest_document" in celery_app.tasks
    assert "researchmate.delete_document" in celery_app.tasks
    assert "researchmate.run_workflow" in celery_app.tasks
    assert "researchmate.run_evaluation" in celery_app.tasks
    assert "researchmate.run_fault_simulation" in celery_app.tasks


def test_ingestion_event_rejects_incomplete_outbox_payload() -> None:
    try:
        IngestionEvent.model_validate({"document_id": "00000000-0000-4000-8000-000000000001"})
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete outbox payload must fail closed")
