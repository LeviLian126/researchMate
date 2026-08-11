"""Assemble the public Postgres repository from aggregate-focused persistence mixins."""

from __future__ import annotations

from researchmate_api.persistence._postgres_chunks import ChunkPersistenceMixin
from researchmate_api.persistence._postgres_conversations import ConversationPersistenceMixin
from researchmate_api.persistence._postgres_core import (
    PostgresRepositoryCore,
    _enum_value,
    _json,
    _psycopg_url,
    _safe_filename,
)
from researchmate_api.persistence._postgres_document_lifecycle import DocumentLifecycleMixin
from researchmate_api.persistence._postgres_feedback_source import PostgresFeedbackSourceMixin
from researchmate_api.persistence._postgres_idempotency import IdempotencyPersistenceMixin
from researchmate_api.persistence._postgres_internal import PostgresInternalMixin
from researchmate_api.persistence._postgres_memory import MemoryPersistenceMixin
from researchmate_api.persistence._postgres_projects import ProjectPersistenceMixin
from researchmate_api.persistence._postgres_quizzes import QuizPersistenceMixin
from researchmate_api.persistence._postgres_runs import RunPersistenceMixin
from researchmate_api.persistence._postgres_uploads import UploadPersistenceMixin

__all__ = [
    "PostgresResearchMateRepository",
    "_enum_value",
    "_json",
    "_psycopg_url",
    "_safe_filename",
]


class PostgresResearchMateRepository(
    ProjectPersistenceMixin,
    UploadPersistenceMixin,
    DocumentLifecycleMixin,
    PostgresFeedbackSourceMixin,
    RunPersistenceMixin,
    QuizPersistenceMixin,
    ConversationPersistenceMixin,
    MemoryPersistenceMixin,
    IdempotencyPersistenceMixin,
    ChunkPersistenceMixin,
    PostgresInternalMixin,
    PostgresRepositoryCore,
):
    """Persist ResearchMate aggregates with explicit user scoping and nested UoW support."""
