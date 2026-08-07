"""Define value objects shared by repository protocols and in-memory adapters."""

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


@dataclass
class ChunkEntry:
    """Represent one retrievable source chunk with ownership and citation metadata."""

    id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID | None
    source_type: SourceType
    source_title: str
    text: str
    page_no: int | None = None
    slide_no: int | None = None
    url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class UploadReservation:
    """Track an in-memory object upload reservation."""

    document_id: UUID
    r2_object_key: str
    request: UploadUrlRequest
    created_at: datetime


@dataclass(frozen=True)
class IdempotencyDecision:
    """Tell an application service whether to execute, replay, wait, or reject."""

    state: Literal["execute", "replay", "in_progress", "mismatch"]
    response: dict[str, Any] | None = None
