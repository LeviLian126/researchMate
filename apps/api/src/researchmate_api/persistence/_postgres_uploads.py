"""Own upload reservations and document lookup queries."""

# ruff: noqa: F401
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
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


class UploadPersistenceMixin:
    """Own upload reservations and document lookup queries."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in PostgresResearchMateRepository.
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]
        _lock_active_project: Callable[[Connection, UUID, UUID], bool]
        upload_url_factory: UploadUrlFactory
        default_project_ttl_days: int

        def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None: ...

    def create_upload_url(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> UploadUrlResponse | None:
        """Reserve an owned document and return its upload destination."""
        document_id = uuid4()
        filename = _safe_filename(payload.filename)
        object_key = (
            f"users/{user.id}/projects/{payload.project_id}/documents/{document_id}/{filename}"
        )
        upload_url = self.upload_url_factory(document_id, object_key, payload)
        expires_at = datetime.now(UTC) + timedelta(days=self.default_project_ttl_days)
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, payload.project_id):
                return None
            project = (
                connection.execute(
                    text(
                        """
                    select id,kind from projects
                    where id=:project_id and user_id=:user_id
                      and status='active' and deleted_at is null
                    """
                    ),
                    {"project_id": payload.project_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if project is None:
                return None
            if project["kind"] == "personal":
                if payload.conversation_id is None:
                    return None
                owned_conversation = connection.execute(
                    text(
                        """
                        select 1 from conversations
                        where id=:conversation_id and project_id=:project_id
                          and user_id=:user_id and deleted_at is null
                        """
                    ),
                    {
                        "conversation_id": payload.conversation_id,
                        "project_id": payload.project_id,
                        "user_id": user.id,
                    },
                ).one_or_none()
                if owned_conversation is None:
                    return None
            elif payload.conversation_id is not None:
                return None
            row = connection.execute(
                text(
                    """
                    insert into documents (
                      id, user_id, project_id, conversation_id, filename, file_type,
                      mime_type, size_bytes,
                      r2_object_key, status, expires_at
                    )
                    select :id, :user_id, p.id, :conversation_id, :filename, :file_type,
                           :mime_type, :size_bytes, :object_key, 'uploaded', :expires_at
                    from projects p
                    where p.id = :project_id and p.user_id = :user_id
                      and p.status = 'active' and p.deleted_at is null
                    returning id
                    """
                ),
                {
                    "id": document_id,
                    "user_id": user.id,
                    "project_id": payload.project_id,
                    "conversation_id": payload.conversation_id,
                    "filename": payload.filename,
                    "file_type": payload.file_type,
                    "mime_type": payload.mime_type,
                    "size_bytes": payload.size_bytes,
                    "object_key": object_key,
                    "expires_at": expires_at,
                },
            ).one_or_none()
            if row is None:
                return None
        return UploadUrlResponse(
            document_id=document_id,
            upload_url=upload_url,
            r2_object_key=object_key,
            expires_in_seconds=600,
        )

    def create_document(
        self, user: CurrentUser, payload: UploadUrlRequest
    ) -> DocumentRecord | None:
        """Resolve the latest matching uploaded document reservation."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id, user_id, project_id, conversation_id, filename, file_type,
                           mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents d
                    where d.user_id = :user_id and d.project_id = :project_id
                      and d.filename = :filename and d.size_bytes = :size_bytes
                      and d.conversation_id is not distinct from :conversation_id
                      and d.deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id = d.project_id and p.user_id = d.user_id
                          and p.status = 'active' and p.deleted_at is null
                      )
                    order by created_at desc
                    limit 1
                    """
                    ),
                    {
                        "user_id": user.id,
                        "project_id": payload.project_id,
                        "conversation_id": payload.conversation_id,
                        "filename": payload.filename,
                        "size_bytes": payload.size_bytes,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is not None:
            return DocumentRecord.model_validate(dict(row))
        reservation = self.create_upload_url(user, payload)
        return None if reservation is None else self.get_document(user, reservation.document_id)

    def list_project_documents(
        self, user: CurrentUser, project_id: UUID
    ) -> list[DocumentRecord] | None:
        """List visible documents belonging to an owned project."""
        if self.get_project(user, project_id) is None:
            return None
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, project_id, conversation_id, filename, file_type,
                           mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents
                    where user_id = :user_id and project_id = :project_id and deleted_at is null
                    order by created_at desc, id
                    """
                ),
                {"user_id": user.id, "project_id": project_id},
            ).mappings()
            return [DocumentRecord.model_validate(dict(row)) for row in rows]

    def list_conversation_documents(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[DocumentRecord] | None:
        """List visible attachments belonging to an owned conversation."""
        with self._transaction(user) as connection:
            owned = connection.execute(
                text(
                    """
                    select project_id from conversations
                    where id=:conversation_id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id and p.user_id=:user_id
                          and p.status='active' and p.deleted_at is null
                      )
                    """
                ),
                {"conversation_id": conversation_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = connection.execute(
                text(
                    """
                    select id,user_id,project_id,conversation_id,filename,file_type,
                           mime_type,size_bytes,status,error_message,expires_at,
                           created_at,updated_at,deleted_at
                    from documents
                    where user_id=:user_id and conversation_id=:conversation_id
                      and deleted_at is null
                    order by created_at desc,id
                    """
                ),
                {"conversation_id": conversation_id, "user_id": user.id},
            ).mappings()
            return [DocumentRecord.model_validate(dict(row)) for row in rows]

    def get_document(self, user: CurrentUser, document_id: UUID) -> DocumentRecord | None:
        """Return one visible document owned by the caller."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id, user_id, project_id, conversation_id, filename, file_type,
                           mime_type, size_bytes,
                           status, error_message, expires_at, created_at, updated_at, deleted_at
                    from documents
                    where id = :document_id and user_id = :user_id and deleted_at is null
                    """
                    ),
                    {"document_id": document_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else DocumentRecord.model_validate(dict(row))
