"""Own conversation lifecycle, messages, and attachment-aware deletion."""

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


class ConversationPersistenceMixin:
    """Own conversation lifecycle, messages, and attachment-aware deletion."""

    def ensure_conversation(
        self,
        user: CurrentUser,
        project_id: UUID,
        conversation_id: UUID | None,
        first_message: str,
    ) -> ConversationSummary | None:
        """Return or create an owned conversation for a query."""
        with self._transaction(user) as connection:
            if not self._lock_active_project(connection, user.id, project_id):
                return None
            if conversation_id is not None:
                row = connection.execute(
                    text(
                        """
                        select id, project_id, title, created_at, updated_at
                        from conversations
                        where id=:id and project_id=:project_id and user_id=:user_id
                          and deleted_at is null
                          and exists (
                            select 1 from projects p
                            where p.id=conversations.project_id
                              and p.user_id=:user_id and p.status='active'
                              and p.deleted_at is null
                          )
                        """
                    ),
                    {
                        "id": conversation_id,
                        "project_id": project_id,
                        "user_id": user.id,
                    },
                ).mappings().one_or_none()
                if row is not None and row["title"] == "New chat":
                    renamed_row = connection.execute(
                        text(
                            """
                            update conversations c
                            set title=:title,updated_at=now()
                            where c.id=:id and c.user_id=:user_id
                              and not exists (
                                select 1 from messages m
                                where m.conversation_id=c.id
                              )
                            returning id,project_id,title,created_at,updated_at
                            """
                        ),
                        {
                            "id": conversation_id,
                            "user_id": user.id,
                            "title": (" ".join(first_message.split())[:120] or "New chat"),
                        },
                    ).mappings().one_or_none()
                    if renamed_row is not None:
                        row = renamed_row
            else:
                row = connection.execute(
                    text(
                        """
                        insert into conversations (id,user_id,project_id,title)
                        select :id,:user_id,p.id,:title
                        from projects p
                        where p.id=:project_id and p.user_id=:user_id
                          and p.status='active' and p.deleted_at is null
                        returning id,project_id,title,created_at,updated_at
                        """
                    ),
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "user_id": user.id,
                        "title": (" ".join(first_message.split())[:120] or "New conversation"),
                    },
                ).mappings().one_or_none()
        return ConversationSummary.model_validate(row) if row else None

    def create_conversation(
        self, user: CurrentUser, project_id: UUID, title: str
    ) -> ConversationSummary | None:
        """Create an owned conversation with the requested title."""
        return self.ensure_conversation(user, project_id, None, title)

    def list_conversations(
        self, user: CurrentUser, project_id: UUID
    ) -> list[ConversationSummary] | None:
        """List conversations in an owned project."""
        with self._transaction(user) as connection:
            project = connection.execute(
                text(
                    """
                    select 1 from projects
                    where id=:project_id and user_id=:user_id
                      and status='active' and deleted_at is null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).one_or_none()
            if project is None:
                return None
            rows = connection.execute(
                text(
                    """
                    select id,project_id,title,created_at,updated_at
                    from conversations
                    where project_id=:project_id and user_id=:user_id and deleted_at is null
                    order by updated_at desc limit 100
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings()
            return [ConversationSummary.model_validate(row) for row in rows]

    def list_all_conversations(self, user: CurrentUser) -> list[ConversationSummary]:
        """List all conversations visible to the caller."""
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select c.id,c.project_id,c.title,c.created_at,c.updated_at
                    from conversations c
                    join projects p on p.id=c.project_id and p.user_id=c.user_id
                    where c.user_id=:user_id and c.deleted_at is null
                      and p.status='active' and p.deleted_at is null
                    order by c.updated_at desc,c.id
                    limit 100
                    """
                ),
                {"user_id": user.id},
            ).mappings()
            return [ConversationSummary.model_validate(row) for row in rows]

    def conversation_messages(
        self, user: CurrentUser, conversation_id: UUID
    ) -> list[ConversationMessage] | None:
        """Return messages belonging to an owned conversation."""
        with self._transaction(user) as connection:
            owned = connection.execute(
                text(
                    """
                    select 1 from conversations
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    """
                ),
                {"id": conversation_id, "user_id": user.id},
            ).one_or_none()
            if owned is None:
                return None
            rows = list(
                connection.execute(
                    text(
                        """
                        select id,conversation_id,role,content,ask_run_id,created_at
                        from messages
                        where conversation_id=:id and user_id=:user_id
                          and role in ('user','assistant')
                        order by created_at,
                                 case role when 'user' then 0 when 'assistant' then 1 else 2 end,
                                 id
                        """
                    ),
                    {"id": conversation_id, "user_id": user.id},
                ).mappings()
            )
            result: list[ConversationMessage] = []
            for row in rows:
                citations = []
                if row["ask_run_id"] is not None:
                    citation_rows = connection.execute(
                        text(
                            """
                            select id,source_type,document_id,chunk_id,page_no,slide_no,
                                   url,quote,claim_id
                            from citations
                            where ask_run_id=:run_id
                            order by created_at,id
                            """
                        ),
                        {"run_id": row["ask_run_id"]},
                    ).mappings()
                    citations = [Citation.model_validate(item) for item in citation_rows]
                result.append(
                    ConversationMessage(
                        id=row["id"],
                        conversation_id=row["conversation_id"],
                        role=row["role"],
                        content=row["content"],
                        citations=citations,
                        created_at=row["created_at"],
                    )
                )
            return result

    def rename_conversation(
        self, user: CurrentUser, conversation_id: UUID, title: str
    ) -> ConversationSummary | None:
        """Rename an owned conversation."""
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update conversations
                    set title=:title,updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    returning id,project_id,title,created_at,updated_at
                    """
                ),
                {"id": conversation_id, "user_id": user.id, "title": title.strip()},
            ).mappings().one_or_none()
        return ConversationSummary.model_validate(row) if row else None

    def delete_conversation(self, user: CurrentUser, conversation_id: UUID) -> bool:
        """Hide an owned conversation and its memory state."""
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update conversations
                    set deleted_at=now(),updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    returning id
                    """
                ),
                {"id": conversation_id, "user_id": user.id},
            ).one_or_none()
        return row is not None

    def delete_conversation_with_attachments(
        self, user: CurrentUser, conversation_id: UUID
    ) -> bool:
        """Schedule attachment cleanup and hide the conversation in one database unit."""
        with self._transaction(user):
            documents = self.list_conversation_documents(user, conversation_id)
            if documents is None:
                return False
            for document in documents:
                if self.delete_document(user, document.id) is None:
                    raise ValueError("conversation attachment cleanup failed")
            if not self.delete_conversation(user, conversation_id):
                raise ValueError("conversation deletion failed")
            return True
