"""Own user and project persistence, including project deletion orchestration."""

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


class ProjectPersistenceMixin:
    """Own user and project persistence, including project deletion orchestration."""

    if TYPE_CHECKING:
        # Provided by sibling mixins composed in PostgresResearchMateRepository.
        from contextlib import AbstractContextManager

        _transaction: Callable[..., AbstractContextManager[Connection]]
        _enqueue_project_deletion: Callable[..., None]
        _insert_job: Callable[..., JobRecord]
        default_project_ttl_days: int

    def ensure_user(self, user: CurrentUser) -> CurrentUser:
        """Persist the caller profile required by owned resources."""
        with self._transaction(user) as connection:
            connection.execute(
                text(
                    """
                    insert into profiles (id, email, provider, role)
                    values (:id, :email, 'supabase', :role)
                    on conflict (id) do update
                    set email = excluded.email, role = excluded.role, updated_at = now()
                    where profiles.id = :id
                    """
                ),
                {"id": user.id, "email": user.email, "role": user.role},
            )
        return user

    def create_project(self, user: CurrentUser, payload: ProjectCreate) -> ProjectRecord:
        """Create an owned workspace project."""
        self.ensure_user(user)
        project_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(days=self.default_project_ttl_days)
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    insert into projects (id, user_id, name, kind, expires_at)
                    select :id, :user_id, :name, 'workspace', :expires_at
                    where exists (select 1 from profiles where id = :user_id)
                    returning id, user_id, name, kind, status, expires_at,
                              created_at, updated_at, deleted_at
                    """
                    ),
                    {
                        "id": project_id,
                        "user_id": user.id,
                        "name": payload.name,
                        "expires_at": expires_at,
                    },
                )
                .mappings()
                .one()
            )
        return ProjectRecord.model_validate(dict(row))

    def ensure_personal_project(self, user: CurrentUser) -> ProjectRecord:
        """Return or create the caller's personal project."""
        self.ensure_user(user)
        project_id = uuid4()
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    insert into projects (id,user_id,name,kind,expires_at)
                    values (:id,:user_id,'Personal chat','personal',null)
                    on conflict (user_id) where kind='personal' and deleted_at is null
                    do update set updated_at=projects.updated_at
                    returning id,user_id,name,kind,status,expires_at,
                              created_at,updated_at,deleted_at
                    """
                    ),
                    {"id": project_id, "user_id": user.id},
                )
                .mappings()
                .one()
            )
        return ProjectRecord.model_validate(dict(row))

    def list_projects(self, user: CurrentUser) -> list[ProjectRecord]:
        """List visible workspace projects owned by the caller."""
        with self._transaction(user) as connection:
            rows = connection.execute(
                text(
                    """
                    select id, user_id, name, kind, status, expires_at,
                           created_at, updated_at, deleted_at
                    from projects
                    where user_id = :user_id and status in ('active', 'deleting')
                      and kind = 'workspace' and deleted_at is null
                    order by updated_at desc, id
                    """
                ),
                {"user_id": user.id},
            ).mappings()
            return [ProjectRecord.model_validate(dict(row)) for row in rows]

    def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None:
        """Return one caller-owned, non-deleted project."""
        with self._transaction(user) as connection:
            row = (
                connection.execute(
                    text(
                        """
                    select id, user_id, name, kind, status, expires_at,
                           created_at, updated_at, deleted_at
                    from projects
                    where id = :project_id and user_id = :user_id and deleted_at is null
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else ProjectRecord.model_validate(dict(row))

    def delete_project(self, user: CurrentUser, project_id: UUID) -> JobRecord | None:
        """Transition an owned project into its recoverable deletion workflow."""
        with self._transaction(user) as connection:
            project = (
                connection.execute(
                    text(
                        """
                    select status,kind from projects
                    where id = :project_id and user_id = :user_id
                      and status in ('active', 'deleting') and deleted_at is null
                    for update
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .mappings()
                .one_or_none()
            )
            if project is None:
                return None
            if project["kind"] == "personal":
                return None
            if project["status"] == "deleting":
                existing = (
                    connection.execute(
                        text(
                            """
                        select id, user_id, project_id, document_id, type, status, progress,
                               error_message, created_at, updated_at
                        from jobs
                        where project_id = :project_id and user_id = :user_id
                          and type = 'delete_project'
                        order by created_at desc, id desc limit 1
                        """
                        ),
                        {"project_id": project_id, "user_id": user.id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None and existing["status"] in {"pending", "running"}:
                    if existing["status"] == "pending":
                        self._enqueue_project_deletion(
                            connection,
                            user_id=user.id,
                            project_id=project_id,
                            job_id=existing["id"],
                            delivery_id=uuid4(),
                        )
                    return JobRecord.model_validate(dict(existing))
                if existing is None or existing["status"] != "failed":
                    return None
            else:
                connection.execute(
                    text(
                        """
                        update projects set status = 'deleting', updated_at = now()
                        where id = :project_id and user_id = :user_id and status = 'active'
                        """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
            connection.execute(
                text(
                    """
                    update jobs
                    set status = 'failed', error_message = 'PROJECT_DELETING',
                      completed_at = now(), updated_at = now(),
                      lease_owner = null, lease_expires_at = null
                    where project_id = :project_id and user_id = :user_id
                      and type = 'parse_and_index_document'
                      and (
                        status = 'pending'
                        or (
                          status = 'running'
                          and (lease_expires_at is null or lease_expires_at <= now())
                        )
                      )
                    """
                ),
                {"project_id": project_id, "user_id": user.id},
            )
            object_keys = (
                connection.execute(
                    text(
                        """
                    select r2_object_key from documents
                    where project_id = :project_id and user_id = :user_id
                      and r2_object_key is not null
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .scalars()
                .all()
            )
            point_ids = (
                connection.execute(
                    text(
                        """
                    select qdrant_point_id from chunks
                    where project_id = :project_id and user_id = :user_id
                      and qdrant_point_id is not null
                    """
                    ),
                    {"project_id": project_id, "user_id": user.id},
                )
                .scalars()
                .all()
            )
            job = self._insert_job(
                connection,
                user=user,
                project_id=project_id,
                document_id=None,
                job_type="delete_project",
                status=JobStatus.PENDING,
                progress=0,
                payload={
                    "r2_object_keys": list(object_keys),
                    "qdrant_point_ids": list(point_ids),
                },
            )
            connection.execute(
                text(
                    """
                    insert into deletion_jobs (id, user_id, project_id, status)
                    values (:id, :user_id, :project_id, 'pending')
                    """
                ),
                {"id": job.id, "user_id": user.id, "project_id": project_id},
            )
            self._enqueue_project_deletion(
                connection,
                user_id=user.id,
                project_id=project_id,
                job_id=job.id,
                delivery_id=job.id,
            )
            return job
