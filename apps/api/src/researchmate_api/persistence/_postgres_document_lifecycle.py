"""Own document completion, deletion, and ingestion job state."""

# ruff: noqa: F401
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from researchmate_api.persistence._postgres_core import _enum_value, _json, _safe_filename
from researchmate_api.schemas.common import (
    Citation,
    CurrentUser,
    ExecutionPlan,
    JobStatus,
    SourceSummary,
    SourceType,
)
from researchmate_api.schemas.conversation import (
    ConversationMessage,
    ConversationSummary,
    RuntimeRerankConfig,
)
from researchmate_api.schemas.document import DocumentRecord, UploadUrlRequest, UploadUrlResponse
from researchmate_api.schemas.job import JobRecord
from researchmate_api.schemas.project import ProjectCreate, ProjectRecord
from researchmate_api.schemas.quiz import QuizQuestion, QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.schemas.trace import DeveloperTrace, ToolCallTrace
from researchmate_api.services.object_storage import (
    ObjectStorageConfigurationError,
    StoredObjectMetadata,
    UploadVerificationError,
)
from researchmate_api.services.store import ChunkEntry, IdempotencyDecision

UploadUrlFactory = Callable[[UUID, str, UploadUrlRequest], str]
ObjectMetadataReader = Callable[[str], StoredObjectMetadata]


class DocumentLifecycleMixin:
    """Own document completion, deletion, and ingestion job state."""

    def complete_document(
        self,
        user: CurrentUser,
        document_id: UUID,
        extracted_text: str | None,
        checksum_sha256: str | None = None,
    ) -> JobRecord | None:
        """Validate an upload and schedule or complete its ingestion lifecycle."""
        if self.object_metadata_reader is None:
            raise ObjectStorageConfigurationError("R2 metadata verification is not configured")
        with self._transaction(user) as connection:
            reserved = connection.execute(
                text(
                    """
                    select d.r2_object_key, d.size_bytes, d.mime_type
                    from documents d
                    join projects p on p.id = d.project_id and p.user_id = d.user_id
                    where d.id = :document_id and d.user_id = :user_id
                      and d.deleted_at is null and p.status = 'active'
                      and p.deleted_at is null
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
        if reserved is None:
            return None
        metadata = self.object_metadata_reader(reserved["r2_object_key"])
        if metadata.size_bytes != reserved["size_bytes"]:
            raise UploadVerificationError(
                "UPLOAD_SIZE_MISMATCH",
                "Uploaded object size does not match the reservation.",
            )
        if metadata.content_type and metadata.content_type != reserved["mime_type"]:
            raise UploadVerificationError(
                "UPLOAD_TYPE_MISMATCH",
                "Uploaded object content type does not match the reservation.",
            )
        with self._transaction(user) as connection:
            owner = connection.execute(
                text(
                    """
                    select project_id from documents
                    where id = :document_id and user_id = :user_id and deleted_at is null
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if owner is None or not self._lock_active_project(
                connection, user.id, owner["project_id"]
            ):
                return None
            document = connection.execute(
                text(
                    """
                    update documents d
                    set status = 'parsing', error_message = null, updated_at = now()
                    from projects p
                    where d.id = :document_id and d.user_id = :user_id
                      and d.project_id = p.id and p.user_id = d.user_id
                      and d.deleted_at is null and p.status = 'active'
                      and p.deleted_at is null and d.status in ('uploaded', 'failed')
                    returning d.project_id, d.r2_object_key
                    """
                ),
                {
                    "document_id": document_id,
                    "user_id": user.id,
                },
            ).mappings().one_or_none()
            if document is None:
                existing = connection.execute(
                    text(
                        """
                        select id, user_id, project_id, document_id, type, status, progress,
                               error_message, created_at, updated_at
                        from jobs
                        where document_id = :document_id and user_id = :user_id
                          and type = 'parse_and_index_document'
                          and exists (
                            select 1 from projects p
                            where p.id = jobs.project_id and p.user_id = jobs.user_id
                              and p.status = 'active' and p.deleted_at is null
                          )
                        order by created_at desc limit 1
                        """
                    ),
                    {"document_id": document_id, "user_id": user.id},
                ).mappings().one_or_none()
                if existing is not None and existing["status"] == "pending":
                    self._enqueue_document_event(
                        connection,
                        event_type="document.ingest.requested",
                        document_id=document_id,
                        user_id=user.id,
                        project_id=existing["project_id"],
                        job_id=existing["id"],
                        delivery_id=uuid4(),
                    )
                return None if existing is None else JobRecord.model_validate(dict(existing))
            job = self._insert_job(
                connection,
                user=user,
                project_id=document["project_id"],
                document_id=document_id,
                job_type="parse_and_index_document",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_key": document["r2_object_key"],
                    "checksum_sha256": checksum_sha256.lower() if checksum_sha256 else None,
                },
            )
            self._enqueue_document_event(
                connection,
                event_type="document.ingest.requested",
                document_id=document_id,
                user_id=user.id,
                project_id=document["project_id"],
                job_id=job.id,
                delivery_id=job.id,
            )
            return job

    def delete_document(self, user: CurrentUser, document_id: UUID) -> JobRecord | None:
        """Transition an owned document into its deletion lifecycle."""
        with self._transaction(user) as connection:
            document = connection.execute(
                text(
                    """
                    select d.project_id, d.r2_object_key, d.deleted_at
                    from documents d
                    join projects p on p.id = d.project_id and p.user_id = d.user_id
                    where d.id = :document_id and d.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    for update of d, p
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if document is None:
                return None
            connection.execute(
                text(
                    """
                    update jobs
                    set status = 'failed', error_message = 'DOCUMENT_DELETING',
                      completed_at = now(), updated_at = now()
                    where document_id = :document_id and user_id = :user_id
                      and type = 'parse_and_index_document' and status = 'pending'
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            )
            existing = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, type, status, progress,
                           error_message, created_at, updated_at
                    from jobs
                    where document_id = :document_id and user_id = :user_id
                      and type = 'delete_document'
                    order by created_at desc, id desc limit 1
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).mappings().one_or_none()
            if document["deleted_at"] is not None and existing is not None:
                if existing["status"] == "pending":
                    self._enqueue_document_event(
                        connection,
                        event_type="document.delete.requested",
                        document_id=document_id,
                        user_id=user.id,
                        project_id=document["project_id"],
                        job_id=existing["id"],
                        delivery_id=uuid4(),
                    )
                    return JobRecord.model_validate(dict(existing))
                if existing["status"] in {"running", "succeeded"}:
                    return JobRecord.model_validate(dict(existing))
                if existing["status"] not in {"failed", "cancelled"}:
                    return None
            elif document["deleted_at"] is None:
                connection.execute(
                    text(
                        """
                        update documents
                        set status = 'deleted', deleted_at = now(), updated_at = now()
                        where id = :document_id and user_id = :user_id
                        """
                    ),
                    {"document_id": document_id, "user_id": user.id},
                )
            point_ids = connection.execute(
                text(
                    """
                    select qdrant_point_id from chunks
                    where document_id = :document_id and user_id = :user_id
                    """
                ),
                {"document_id": document_id, "user_id": user.id},
            ).scalars().all()
            job = self._insert_job(
                connection,
                user=user,
                project_id=document["project_id"],
                document_id=document_id,
                job_type="delete_document",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_key": document["r2_object_key"],
                    "qdrant_point_ids": list(point_ids),
                },
            )
            connection.execute(
                text(
                    """
                    insert into deletion_jobs (id, user_id, project_id, document_id, status)
                    values (:id, :user_id, :project_id, :document_id, 'pending')
                    """
                ),
                {
                    "id": job.id,
                    "user_id": user.id,
                    "project_id": document["project_id"],
                    "document_id": document_id,
                },
            )
            self._enqueue_document_event(
                connection,
                event_type="document.delete.requested",
                document_id=document_id,
                user_id=user.id,
                project_id=document["project_id"],
                job_id=job.id,
                delivery_id=job.id,
            )
            return job

    def get_job(self, user: CurrentUser, job_id: UUID) -> JobRecord | None:
        """Return one background job visible to the caller."""
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, project_id, document_id, type, status, progress,
                           error_message, created_at, updated_at
                    from jobs where id = :job_id and user_id = :user_id
                    """
                ),
                {"job_id": job_id, "user_id": user.id},
            ).mappings().one_or_none()
        return None if row is None else JobRecord.model_validate(dict(row))
