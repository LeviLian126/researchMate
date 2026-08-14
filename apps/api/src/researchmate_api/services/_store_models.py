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
    section_title: str | None = None
    section_path: tuple[str, ...] = ()
    chunk_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    has_vector: bool = True
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class WikiPage:
    """Represent one LLM-compiled wiki page with source provenance and links.

    Wiki pages are derived from lightweight document chunks by the LLM compiler.
    They replace the original chunks in the retrieval pipeline so that short
    documents enter the query context as structured, linkable knowledge entries
    rather than raw text fragments. The original document text is preserved in
    the document store; wiki pages are a derived explanation layer.
    """

    id: UUID
    user_id: UUID
    project_id: UUID
    document_id: UUID
    title: str
    page_type: str
    content: str
    aliases: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    source_chunk_ids: list[UUID] = field(default_factory=list)
    references: list[dict[str, object]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
