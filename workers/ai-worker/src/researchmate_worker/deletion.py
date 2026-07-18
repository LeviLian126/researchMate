from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Engine, text

from researchmate_api.services.object_storage import ObjectStorageRequestError
from researchmate_api.services.qdrant_store import VectorStoreRequestError
from researchmate_worker.ingestion import IngestionFailure


class DocumentDeletionEvent(BaseModel):
    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID


@dataclass(frozen=True)
class DeletionRecord:
    job_id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID
    r2_object_key: str
    qdrant_point_ids: list[str]
    attempts: int


class DeletionStore(Protocol):
    def claim(
        self, event: DocumentDeletionEvent, *, worker_id: str, lease_seconds: int
    ) -> DeletionRecord | None: ...

    def mark_ready(self, record: DeletionRecord, *, worker_id: str) -> None: ...

    def mark_retryable(self, record: DeletionRecord, *, worker_id: str, code: str) -> None: ...

    def mark_failed(self, record: DeletionRecord, *, worker_id: str, code: str) -> None: ...


class ObjectDeletion(Protocol):
    def delete(self, object_key: str) -> None: ...


class VectorDeletion(Protocol):
    def delete_points(
        self, point_ids: list[str], *, user_id: str, project_id: str
    ) -> None: ...


class SqlDeletionStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def claim(
        self,
        event: DocumentDeletionEvent,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> DeletionRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    update jobs as j
                    set status = 'running', progress = greatest(j.progress, 10),
                      attempts = j.attempts + 1, lease_owner = :worker_id,
                      lease_expires_at = now() + make_interval(secs => :lease_seconds),
                      started_at = coalesce(j.started_at, now()), updated_at = now(),
                      error_message = null
                    from documents as d
                    where j.id = :job_id and j.type = 'delete_document'
                      and j.user_id = :user_id and j.project_id = :project_id
                      and j.document_id = :document_id
                      and d.id = j.document_id and d.user_id = j.user_id
                      and d.project_id = j.project_id and d.status = 'deleted'
                      and (
                        j.status = 'pending'
                        or (j.status = 'running' and j.lease_expires_at < now())
                      )
                    returning j.id as job_id, j.user_id, j.project_id, j.document_id,
                      j.payload ->> 'r2_object_key' as r2_object_key,
                      coalesce(j.payload -> 'qdrant_point_ids', '[]'::jsonb) as qdrant_point_ids,
                      j.attempts
                    """
                ),
                {
                    "job_id": event.job_id,
                    "user_id": event.user_id,
                    "project_id": event.project_id,
                    "document_id": event.document_id,
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                },
            ).mappings().one_or_none()
        if row is None:
            return None
        values = dict(row)
        values["qdrant_point_ids"] = list(values["qdrant_point_ids"] or [])
        return DeletionRecord(**values)

    def mark_ready(self, record: DeletionRecord, *, worker_id: str) -> None:
        with self.engine.begin() as connection:
            locked = connection.execute(
                text(
                    """
                    select 1 from jobs where id = :job_id and status = 'running'
                      and lease_owner = :worker_id and lease_expires_at > now()
                    for update
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id},
            ).one_or_none()
            if locked is None:
                raise IngestionFailure("JOB_LEASE_LOST", retryable=True)
            connection.execute(
                text("delete from document_pages where document_id = :document_id"),
                {"document_id": record.document_id},
            )
            connection.execute(
                text("delete from chunks where document_id = :document_id"),
                {"document_id": record.document_id},
            )
            connection.execute(
                text(
                    """
                    update deletion_jobs set status = 'succeeded', completed_at = now(),
                      error_message = null where id = :job_id
                    """
                ),
                {"job_id": record.job_id},
            )
            connection.execute(
                text(
                    """
                    update jobs set status = 'succeeded', progress = 100, completed_at = now(),
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where id = :job_id
                    """
                ),
                {"job_id": record.job_id},
            )

    def mark_retryable(self, record: DeletionRecord, *, worker_id: str, code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update jobs set status = 'pending', error_message = :code,
                      lease_owner = null, lease_expires_at = null, updated_at = now()
                    where id = :job_id and lease_owner = :worker_id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id, "code": code[:80]},
            )

    def mark_failed(self, record: DeletionRecord, *, worker_id: str, code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update jobs set status = 'failed', error_message = :code,
                      lease_owner = null, lease_expires_at = null, completed_at = now(),
                      updated_at = now() where id = :job_id and lease_owner = :worker_id
                    """
                ),
                {"job_id": record.job_id, "worker_id": worker_id, "code": code[:80]},
            )
            connection.execute(
                text(
                    """
                    update deletion_jobs set status = 'failed', error_message = :code,
                      completed_at = now() where id = :job_id
                    """
                ),
                {"job_id": record.job_id, "code": code[:80]},
            )


class DocumentDeletionService:
    def __init__(
        self,
        *,
        store: DeletionStore,
        object_storage: ObjectDeletion,
        vector_store: VectorDeletion,
        lease_seconds: int,
        max_attempts: int,
    ) -> None:
        self.store = store
        self.object_storage = object_storage
        self.vector_store = vector_store
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def handle(self, event: DocumentDeletionEvent, *, worker_id: str) -> str:
        record = self.store.claim(event, worker_id=worker_id, lease_seconds=self.lease_seconds)
        if record is None:
            return "not_claimed"
        try:
            self.vector_store.delete_points(
                record.qdrant_point_ids,
                user_id=str(record.user_id),
                project_id=str(record.project_id),
            )
            self.object_storage.delete(record.r2_object_key)
            self.store.mark_ready(record, worker_id=worker_id)
            return "succeeded"
        except ObjectStorageRequestError as exc:
            self._record_failure(record, worker_id, "OBJECT_DELETE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("OBJECT_DELETE_UNAVAILABLE", retryable=exc.retryable) from exc
        except VectorStoreRequestError as exc:
            self._record_failure(record, worker_id, "VECTOR_DELETE_UNAVAILABLE", exc.retryable)
            raise IngestionFailure("VECTOR_DELETE_UNAVAILABLE", retryable=exc.retryable) from exc
        except IngestionFailure:
            raise
        except Exception as exc:
            self._record_failure(record, worker_id, "DELETE_INTERNAL_ERROR", False)
            raise IngestionFailure("DELETE_INTERNAL_ERROR", retryable=False) from exc

    def _record_failure(
        self,
        record: DeletionRecord,
        worker_id: str,
        code: str,
        retryable: bool,
    ) -> None:
        if retryable and record.attempts < self.max_attempts:
            self.store.mark_retryable(record, worker_id=worker_id, code=code)
        else:
            self.store.mark_failed(record, worker_id=worker_id, code=code)
