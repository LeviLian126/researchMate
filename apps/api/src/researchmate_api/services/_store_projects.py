"""Own in-memory users and project lifecycle state."""

# ruff: noqa: F401
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from researchmate_api.schemas.common import (
    Citation,
    CurrentUser,
    DocumentStatus,
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
from researchmate_api.schemas.quiz import QuizSet
from researchmate_api.schemas.sources import RunSourcesResponse
from researchmate_api.services._store_models import (
    ChunkEntry,
    IdempotencyDecision,
    UploadReservation,
)


class ProjectStoreMixin:
    """Own in-memory users and project lifecycle state."""

    def ensure_user(self, user: CurrentUser) -> CurrentUser:
        """Persist the caller profile required by owned resources."""
        with self._lock:
            self.profiles[user.id] = user
            return user

    def create_project(self, user: CurrentUser, payload: ProjectCreate) -> ProjectRecord:
        """Create an owned workspace project."""
        with self._lock:
            self.ensure_user(user)
            now = datetime.now(UTC)
            project = ProjectRecord(
                id=uuid4(),
                user_id=user.id,
                name=payload.name,
                kind="workspace",
                status="active",
                expires_at=now + timedelta(days=7),
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            self.projects[project.id] = project
            return project

    def ensure_personal_project(self, user: CurrentUser) -> ProjectRecord:
        """Return or create the caller's personal project."""
        with self._lock:
            self.ensure_user(user)
            existing = next(
                (
                    project
                    for project in self.projects.values()
                    if project.user_id == user.id
                    and project.kind == "personal"
                    and project.deleted_at is None
                ),
                None,
            )
            if existing is not None:
                return existing
            now = datetime.now(UTC)
            project = ProjectRecord(
                id=uuid4(),
                user_id=user.id,
                name="Personal chat",
                kind="personal",
                status="active",
                expires_at=None,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            self.projects[project.id] = project
            return project

    def list_projects(self, user: CurrentUser) -> list[ProjectRecord]:
        """List visible workspace projects owned by the caller."""
        with self._lock:
            return [
                project
                for project in self.projects.values()
                if project.user_id == user.id
                and project.kind == "workspace"
                and project.deleted_at is None
            ]

    def get_project(self, user: CurrentUser, project_id: UUID) -> ProjectRecord | None:
        """Return one caller-owned, non-deleted project."""
        with self._lock:
            project = self.projects.get(project_id)
            if project is None or project.user_id != user.id or project.deleted_at is not None:
                return None
            return project

    def delete_project(self, user: CurrentUser, project_id: UUID) -> JobRecord | None:
        """Delete an owned workspace and its process-local dependent state."""
        with self._lock:
            project = self.get_project(user, project_id)
            if project is None or project.kind == "personal":
                return None
            now = datetime.now(UTC)
            self.projects[project_id] = project.model_copy(
                update={"status": "deleted", "deleted_at": now, "updated_at": now}
            )
            for document in list(self.documents.values()):
                if document.project_id == project_id and document.user_id == user.id:
                    self.documents[document.id] = document.model_copy(
                        update={"status": DocumentStatus.DELETED, "deleted_at": now, "updated_at": now}
                    )
            for chunk_id, chunk in list(self.chunks.items()):
                if chunk.project_id == project_id and chunk.user_id == user.id:
                    del self.chunks[chunk_id]
            job = self._create_job_locked(
                user=user,
                project_id=project_id,
                document_id=None,
                job_type="delete_project",
                status=JobStatus.SUCCEEDED,
                progress=100,
            )
            return job
