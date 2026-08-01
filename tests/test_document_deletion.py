"""Verify document and project deletion order across external projections."""

from uuid import UUID

import pytest
from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_worker.deletion import (
    DeletionRecord,
    DocumentDeletionEvent,
    DocumentDeletionService,
    ProjectDeletionEvent,
    ProjectDeletionRecord,
    ProjectDeletionService,
)
from researchmate_worker.ingestion import IngestionFailure

EVENT = DocumentDeletionEvent(
    job_id=UUID("30000000-0000-4000-8000-000000000001"),
    user_id=UUID("30000000-0000-4000-8000-000000000002"),
    project_id=UUID("30000000-0000-4000-8000-000000000003"),
    document_id=UUID("30000000-0000-4000-8000-000000000004"),
)
PROJECT_EVENT = ProjectDeletionEvent(
    job_id=UUID("50000000-0000-4000-8000-000000000001"),
    user_id=UUID("50000000-0000-4000-8000-000000000002"),
    project_id=UUID("50000000-0000-4000-8000-000000000003"),
)


class FakeStore:
    """Record deletion state transitions made by the service."""
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
    """Record object-storage deletions and inject configured failures."""
    def __init__(self, error=None):
        self.error = error
        self.deleted = None

    def delete(self, object_key):
        if self.error:
            raise self.error
        self.deleted = object_key


class FakeVectors:
    """Record vector-projection deletion requests."""
    def __init__(self):
        self.deleted = None
        self.deleted_project = None

    def delete_points(self, point_ids, *, user_id, project_id):
        self.deleted = (point_ids, user_id, project_id)

    def delete_project_points(self, *, user_id, project_id):
        self.deleted_project = (user_id, project_id)


def test_deletion_removes_external_projections_before_finalizing_database() -> None:
    """Require external cleanup before final database deletion state."""
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
    """Keep cleanup retryable when object deletion transiently fails."""
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


def test_project_deletion_removes_all_external_objects_before_database_cascade() -> None:
    """Require project objects to disappear before the database cascade."""
    class ProjectStore(FakeStore):
        def __init__(self):
            super().__init__()
            self.record = ProjectDeletionRecord(
                **PROJECT_EVENT.model_dump(),
                r2_object_keys=["private/one.pdf", "private/two.docx"],
                qdrant_point_ids=["point-1", "point-2"],
                attempts=1,
            )

    class ProjectObjects:
        def __init__(self):
            self.deleted = []

        def delete(self, object_key):
            self.deleted.append(object_key)

    store, objects, vectors = ProjectStore(), ProjectObjects(), FakeVectors()
    service = ProjectDeletionService(
        store=store,
        object_storage=objects,
        vector_store=vectors,
        lease_seconds=120,
        max_attempts=3,
    )

    assert service.handle(PROJECT_EVENT, worker_id="worker-1") == "succeeded"
    assert objects.deleted == ["private/one.pdf", "private/two.docx"]
    assert vectors.deleted_project == (
        str(PROJECT_EVENT.user_id),
        str(PROJECT_EVENT.project_id),
    )
    assert store.ready is True
