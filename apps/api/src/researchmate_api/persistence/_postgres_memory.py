"""Own runtime rerank configuration and durable conversation/project memory."""

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


class MemoryPersistenceMixin:
    """Own runtime rerank configuration and durable conversation/project memory."""

    def get_runtime_rerank_config(self) -> RuntimeRerankConfig:
        """Return the active runtime rerank configuration."""
        with self._transaction() as connection:
            row = connection.execute(
                text(
                    """
                    select provider,version,updated_at,updated_by
                    from runtime_ai_config where config_key='rerank'
                    """
                )
            ).mappings().one()
        return RuntimeRerankConfig.model_validate(row)

    def update_runtime_rerank_config(
        self, user: CurrentUser, provider: str, expected_version: int
    ) -> RuntimeRerankConfig | None:
        """Update rerank configuration using optimistic version control."""
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    update runtime_ai_config
                    set provider=:provider,version=version+1,updated_at=now(),updated_by=:user_id
                    where config_key='rerank' and version=:expected_version
                    returning provider,version,updated_at,updated_by
                    """
                ),
                {
                    "provider": provider,
                    "user_id": user.id,
                    "expected_version": expected_version,
                },
            ).mappings().one_or_none()
        return RuntimeRerankConfig.model_validate(row) if row else None

    def conversation_summary(
        self, user: CurrentUser, conversation_id: UUID
    ) -> tuple[str | None, int] | None:
        """Return the saved rolling summary for an owned conversation."""
        with self._transaction(user) as connection:
            row = connection.execute(
                text(
                    """
                    select summary_text,summary_message_count
                    from conversations
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
            ).mappings().one_or_none()
        if row is None:
            return None
        return row["summary_text"], int(row["summary_message_count"])

    def update_conversation_summary(
        self,
        user: CurrentUser,
        conversation_id: UUID,
        summary: str,
        message_count: int,
    ) -> bool:
        """Replace an owned conversation summary at the expected message count."""
        from researchmate_api.services.retrieval import estimate_tokens

        with self._transaction(user) as connection:
            updated = connection.execute(
                text(
                    """
                    update conversations
                    set summary_text=:summary,
                        summary_token_count=:tokens,
                        summary_message_count=:message_count,
                        summary_updated_at=now()
                    where id=:id and user_id=:user_id and deleted_at is null
                      and exists (
                        select 1 from projects p
                        where p.id=conversations.project_id
                          and p.user_id=:user_id and p.status='active'
                          and p.deleted_at is null
                      )
                    """
                ),
                {
                    "summary": summary,
                    "tokens": estimate_tokens(summary),
                    "message_count": message_count,
                    "id": conversation_id,
                    "user_id": user.id,
                },
            )
        return bool(updated.rowcount)

    def project_memory_context(
        self,
        user: CurrentUser,
        project_id: UUID,
        exclude_conversation_id: UUID,
        limit: int = 16,
    ) -> list[ConversationMessage] | None:
        """Return recent conversation memory for an owned project."""
        with self._transaction(user) as connection:
            project = connection.execute(
                text(
                    """
                    select kind from projects
                    where id=:project_id and user_id=:user_id
                      and status='active' and deleted_at is null
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            ).mappings().one_or_none()
            if project is None:
                return None
            if project["kind"] != "workspace":
                return []
            rows = list(
                connection.execute(
                    text(
                        """
                        (
                          select gen_random_uuid() as id,c.id as conversation_id,
                                 'assistant'::text as role,
                                 ('Project conversation summary: ' || c.summary_text) as content,
                                 c.summary_updated_at as created_at
                          from conversations c
                          where c.project_id=:project_id and c.user_id=:user_id
                            and c.id<>:exclude_id and c.deleted_at is null
                            and c.summary_text is not null
                          order by c.summary_updated_at desc nulls last
                          limit 4
                        )
                        union all
                        (
                          select m.id,m.conversation_id,m.role,m.content,m.created_at
                          from messages m
                          join conversations c on c.id=m.conversation_id
                          where m.project_id=:project_id and m.user_id=:user_id
                            and m.conversation_id<>:exclude_id
                            and c.deleted_at is null
                            and m.role in ('user','assistant')
                          order by m.created_at desc,m.id desc
                          limit :limit
                        )
                        order by created_at
                        """
                    ),
                    {
                        "project_id": project_id,
                        "user_id": user.id,
                        "exclude_id": exclude_conversation_id,
                        "limit": max(1, min(limit, 40)),
                    },
                ).mappings()
            )
            return [
                ConversationMessage(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    content=row["content"],
                    citations=[],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
