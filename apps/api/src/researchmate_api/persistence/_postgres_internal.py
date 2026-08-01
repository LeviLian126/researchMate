"""Own repository-internal queue, locking, citation, and job SQL helpers."""

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


class PostgresInternalMixin:
    """Own repository-internal queue, locking, citation, and job SQL helpers."""

    def _enqueue_project_deletion(
        self,
        connection: Connection,
        *,
        user_id: UUID,
        project_id: UUID,
        job_id: UUID,
        delivery_id: UUID,
    ) -> None:
        """Persist one independently deduplicated delivery for a project-deletion job."""
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type, aggregate_id, event_type, payload, idempotency_key
                )
                select
                  'project', :project_id, 'project.delete.requested',
                  cast(:payload as jsonb), :idempotency_key
                where not exists (
                  select 1 from outbox_events pending
                  where pending.event_type = 'project.delete.requested'
                    and pending.payload ->> 'job_id' = :job_id
                    and pending.status in ('pending', 'publishing')
                )
                  and not exists (
                    select 1 from outbox_events recent
                    where recent.event_type = 'project.delete.requested'
                      and recent.payload ->> 'job_id' = :job_id
                      and recent.created_at > now() - interval '30 seconds'
                  )
                  and (
                    select count(*) from outbox_events prior
                    where prior.event_type = 'project.delete.requested'
                      and prior.payload ->> 'job_id' = :job_id
                  ) < 5
                on conflict (idempotency_key) do nothing
                """
            ),
            {
                "project_id": project_id,
                "payload": _json(
                    {
                        "job_id": str(job_id),
                        "user_id": str(user_id),
                        "project_id": str(project_id),
                    }
                ),
                "job_id": str(job_id),
                "idempotency_key": f"project:{project_id}:delete:{job_id}:{delivery_id}",
            },
        )

    def _enqueue_document_event(
        self,
        connection: Connection,
        *,
        event_type: str,
        document_id: UUID,
        user_id: UUID,
        project_id: UUID,
        job_id: UUID,
        delivery_id: UUID,
    ) -> None:
        """Persist one independently deduplicated ingestion or deletion delivery."""
        action = "ingest" if event_type == "document.ingest.requested" else "delete"
        connection.execute(
            text(
                """
                insert into outbox_events (
                  aggregate_type, aggregate_id, event_type, payload, idempotency_key
                )
                select
                  'document', :document_id, :event_type,
                  cast(:payload as jsonb), :idempotency_key
                where not exists (
                  select 1 from outbox_events pending
                  where pending.event_type = :event_type
                    and pending.payload ->> 'job_id' = :job_id
                    and pending.status in ('pending', 'publishing')
                )
                  and not exists (
                    select 1 from outbox_events recent
                    where recent.event_type = :event_type
                      and recent.payload ->> 'job_id' = :job_id
                      and recent.created_at > now() - interval '30 seconds'
                  )
                  and (
                    select count(*) from outbox_events prior
                    where prior.event_type = :event_type
                      and prior.payload ->> 'job_id' = :job_id
                  ) < 5
                on conflict (idempotency_key) do nothing
                """
            ),
            {
                "document_id": document_id,
                "event_type": event_type,
                "job_id": str(job_id),
                "payload": _json(
                    {
                        "job_id": str(job_id),
                        "user_id": str(user_id),
                        "project_id": str(project_id),
                        "document_id": str(document_id),
                    }
                ),
                "idempotency_key": (
                    f"document:{document_id}:{action}:{job_id}:{delivery_id}"
                ),
            },
        )

    def _lock_active_project(
        connection: Connection, user_id: UUID, project_id: UUID
    ) -> bool:
        """Serialize project-scoped writes against the active-to-deleting transition."""
        row = connection.execute(
            text(
                """
                select 1 from projects
                where id = :project_id and user_id = :user_id
                  and status = 'active' and deleted_at is null
                for update
                """
            ),
            {"project_id": project_id, "user_id": user_id},
        ).one_or_none()
        return row is not None

    def _load_citations(
        self, connection: Connection, user_id: UUID, run_id: UUID
    ) -> list[Citation]:
        """Load citations persisted for one execution run."""
        rows = connection.execute(
            text(
                """
                select c.id, c.source_type, c.document_id, c.chunk_id, c.page_no, c.slide_no,
                       c.url, c.quote, c.claim_id
                from citations c
                join ask_runs ar on ar.id = c.ask_run_id
                where c.ask_run_id = :run_id and ar.user_id = :user_id
                order by c.created_at, c.id
                """
            ),
            {"run_id": run_id, "user_id": user_id},
        ).mappings()
        return [Citation.model_validate(dict(row)) for row in rows]

    def _insert_job(
        self,
        connection: Connection,
        *,
        user: CurrentUser,
        project_id: UUID | None,
        document_id: UUID | None,
        job_type: str,
        status: JobStatus,
        progress: int,
        error_message: str | None = None,
        payload: dict | None = None,
    ) -> JobRecord:
        """Insert and map one durable background job."""
        row = connection.execute(
            text(
                """
                insert into jobs (
                  id, user_id, project_id, document_id, type, status, progress, payload, error_message
                ) values (
                  :id, :user_id, :project_id, :document_id, :type, :status, :progress,
                  cast(:payload as jsonb), :error
                )
                returning id, user_id, project_id, document_id, type, status, progress,
                          error_message, created_at, updated_at
                """
            ),
            {
                "id": uuid4(),
                "user_id": user.id,
                "project_id": project_id,
                "document_id": document_id,
                "type": job_type,
                "status": _enum_value(status),
                "progress": progress,
                "payload": _json(payload or {}),
                "error": error_message,
            },
        ).mappings().one()
        return JobRecord.model_validate(dict(row))
