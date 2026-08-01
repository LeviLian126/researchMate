"""Provide lock ownership and shared mutable state for the in-memory repository."""

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
from researchmate_api.schemas.trace import DeveloperTrace
from researchmate_api.services._store_models import (
    ChunkEntry,
    IdempotencyDecision,
    UploadReservation,
)


class InMemoryStoreCore:
    """Initialize and reset thread-safe state shared by aggregate-focused mixins."""

    def __init__(self) -> None:
        """Initialize repository dependencies and state."""
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        """Clear process-local repository state for isolated development or tests."""
        with self._lock:
            self.profiles: dict[UUID, CurrentUser] = {}
            self.projects: dict[UUID, ProjectRecord] = {}
            self.documents: dict[UUID, DocumentRecord] = {}
            self.jobs: dict[UUID, JobRecord] = {}
            self.uploads: dict[UUID, UploadReservation] = {}
            self.chunks: dict[UUID, ChunkEntry] = {}
            self.run_sources: dict[UUID, RunSourcesResponse] = {}
            self.traces: dict[UUID, DeveloperTrace] = {}
            self.quiz_sets: dict[UUID, QuizSet] = {}
            self.project_quiz_sets: dict[UUID, list[UUID]] = {}
            self.api_usage: dict[tuple[UUID, str, str], int] = {}
            self.idempotency_records: dict[tuple[UUID, str, str], dict[str, Any]] = {}
            self.conversations: dict[UUID, ConversationSummary] = {}
            self.conversation_items: dict[UUID, list[ConversationMessage]] = {}
            self.conversation_summaries: dict[UUID, tuple[str, int]] = {}
            now = datetime.now(UTC)
            self.runtime_rerank_config = RuntimeRerankConfig(
                provider="auto", version=1, updated_at=now, updated_by=None
            )

    def _create_job_locked(
        self,
        user: CurrentUser,
        project_id: UUID | None,
        document_id: UUID | None,
        job_type: str,
        status: JobStatus,
        progress: int,
        error_message: str | None = None,
    ) -> JobRecord:
        """Create a job while the in-memory repository lock is held."""
        now = datetime.now(UTC)
        job = JobRecord(
            id=uuid4(),
            user_id=user.id,
            project_id=project_id,
            document_id=document_id,
            type=job_type,
            status=status,
            progress=progress,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        return job
