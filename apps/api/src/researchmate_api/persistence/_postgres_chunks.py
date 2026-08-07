"""Own authorized chunk retrieval for project and conversation contexts."""

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


class ChunkPersistenceMixin:
    """Own authorized chunk retrieval for project and conversation contexts."""

    def project_chunks(self, user: CurrentUser, project_id: UUID) -> list[ChunkEntry] | None:
        """Return retrievable chunks from ready sources in an owned project."""
        if self.get_project(user, project_id) is None:
            return None
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select c.id, c.user_id, c.project_id, c.document_id, c.source_type,
                           c.source_title, c.text, c.page_no, c.slide_no, c.url, c.created_at
                    from chunks c
                    left join documents d on d.id=c.document_id and d.user_id=c.user_id
                    where c.user_id = :user_id and c.project_id = :project_id
                      and (
                        c.source_type <> 'local_doc'
                        or (d.status = 'ready' and d.deleted_at is null)
                      )
                    order by c.created_at, c.id
                    """
                ),
                {"user_id": user.id, "project_id": project_id},
            ).mappings()
            return [ChunkEntry(**dict(row)) for row in rows]

    def conversation_chunks(
        self, user: CurrentUser, project_id: UUID, conversation_id: UUID
    ) -> list[ChunkEntry] | None:
        """Return retrievable ready-document chunks for an owned conversation."""
        with self._transaction(user) as connection:
            owned = connection.execute(
                text(
                    """
                    select 1 from conversations c
                    join projects p on p.id=c.project_id and p.user_id=c.user_id
                    where c.id=:conversation_id and c.project_id=:project_id
                      and c.user_id=:user_id and c.deleted_at is null
                      and p.status='active' and p.deleted_at is null
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "user_id": user.id,
                },
            ).one_or_none()
            if owned is None:
                return None
            rows = connection.execute(
                text(
                    """
                    select c.id,c.user_id,c.project_id,c.document_id,c.source_type,
                           c.source_title,c.text,c.page_no,c.slide_no,c.url,c.created_at
                    from chunks c
                    join documents d on d.id=c.document_id and d.user_id=c.user_id
                    where c.user_id=:user_id and c.project_id=:project_id
                      and d.conversation_id=:conversation_id
                      and d.status='ready' and d.deleted_at is null
                    order by c.created_at,c.id
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "user_id": user.id,
                },
            ).mappings()
            return [ChunkEntry(**dict(row)) for row in rows]

    def get_chunks_by_ids(
        self, user: CurrentUser, project_id: UUID, chunk_ids: list[UUID]
    ) -> list[ChunkEntry] | None:
        """Return requested visible chunks while preserving caller order."""
        if self.get_project(user, project_id) is None:
            return None
        if not chunk_ids:
            return []
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                   select id, user_id, project_id, document_id, source_type, source_title,
                          text, page_no, slide_no, url, created_at
                   from chunks
                   where user_id = :user_id and project_id = :project_id
                     and id = any(:chunk_ids) and source_type = 'local_doc'
                      and exists (
                        select 1 from documents d
                        where d.id = chunks.document_id and d.user_id = chunks.user_id
                          and d.status = 'ready' and d.deleted_at is null
                      )
                    """
                ),
                {"user_id": user.id, "project_id": project_id, "chunk_ids": chunk_ids},
            ).mappings()
            by_id = {row["id"]: ChunkEntry(**dict(row)) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]
