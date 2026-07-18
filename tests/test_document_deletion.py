from uuid import UUID

import pytest

from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_worker.deletion import (
    DeletionRecord,
    DocumentDeletionEvent,
    DocumentDeletionService,
)
from researchmate_worker.ingestion import IngestionFailure


EVENT = DocumentDeletionEvent(
    job_id=UUID("30000000-0000-4000-8000-000000000001"),
    user_id=UUID("30000000-0000-4000-8000-000000000002"),
    project_id=UUID("30000000-0000-4000-8000-000000000003"),
    document_id=UUID("30000000-0000-4000-8000-000000000004"),
)


class FakeStore:
    def __init__(self, attempts=1):
        self.record = DeletionRecord(
            **EVENT.model_dump(),
            r2_object_key="private/evidence.pdf",
            qdrant_point_ids=["point-1", "point-2"],
            attempts=attempts,
        )
        self.ready = False
        self.retry = None
        self.failed = None

    def claim(self, event, *, worker_id, lease_seconds):
        return self.record

    def mark_ready(self, record, *, worker_id):
        self.ready = True

    def mark_retryable(self, record, *, worker_id, code):
        self.retry = code

    def mark_failed(self, record, *, worker_id, code):
        self.failed = code


class FakeObjects:
    def __init__(self, error=None):
        self.error = error
        self.deleted = None

    def delete(self, object_key):
        if self.error:
            raise self.error
        self.deleted = object_key


class FakeVectors:
    def __init__(self):
        self.deleted = None

    def delete_points(self, point_ids, *, user_id, project_id):
        self.deleted = (point_ids, user_id, project_id)


def test_deletion_removes_external_projections_before_finalizing_database() -> None:
    store, objects, vectors = FakeStore(), FakeObjects(), FakeVectors()
    service = DocumentDeletionService(
        store=store,
        object_storage=objects,
        vector_store=vectors,
        lease_seconds=120,
        max_attempts=3,
    )

    assert service.handle(EVENT, worker_id="worker-1") == "succeeded"
    assert vectors.deleted == (
        ["point-1", "point-2"],
        str(EVENT.user_id),
        str(EVENT.project_id),
    )
    assert objects.deleted == "private/evidence.pdf"
    assert store.ready is True


def test_retryable_object_delete_keeps_database_cleanup_pending() -> None:
    store = FakeStore(attempts=1)
    objects = FakeObjects(error=ObjectStorageRequestError("delete", retryable=True))
    service = DocumentDeletionService(
        store=store,
        object_storage=objects,
        vector_store=FakeVectors(),
        lease_seconds=120,
        max_attempts=3,
    )

    with pytest.raises(IngestionFailure) as failure:
        service.handle(EVENT, worker_id="worker-1")

    assert failure.value.retryable is True
    assert store.retry == "OBJECT_DELETE_UNAVAILABLE"
    assert store.ready is False
