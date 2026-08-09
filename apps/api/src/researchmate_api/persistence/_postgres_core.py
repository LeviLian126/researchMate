"""Provide shared SQLAlchemy configuration, transactions, and serialization helpers."""

# ruff: noqa: F401

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

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
from researchmate_api.schemas.document import (
    DocumentRecord,
    UploadUrlRequest,
    UploadUrlResponse,
    safe_upload_filename,
)
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
# Object metadata readers accept the optional declared_mime_type keyword used by callers; the
# ... form preserves that call shape through typing without exposing internal kwargs.
ObjectMetadataReader = Callable[..., StoredObjectMetadata]


def _enum_value(value: str | Enum) -> str:
    """Normalize schema enum values before binding them to SQL."""
    return str(value.value if isinstance(value, Enum) else value)


def _json(value: object) -> str:
    """Serialize values into the compact JSON representation stored by Postgres."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def _safe_filename(filename: str) -> str:
    """Sanitize an uploaded filename for use inside an object-storage key."""
    return safe_upload_filename(filename)


def _psycopg_url(database_url: str) -> str:
    """Normalize common Postgres URLs to SQLAlchemy's psycopg driver URL."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class PostgresRepositoryCore:
    """Configure the engine and preserve one nested transaction per request context."""

    def __init__(
        self,
        engine: Engine,
        *,
        default_project_ttl_days: int = 7,
        upload_url_factory: UploadUrlFactory | None = None,
        object_metadata_reader: ObjectMetadataReader | None = None,
    ) -> None:
        """Initialize repository dependencies and state."""
        self.engine = engine
        self.default_project_ttl_days = default_project_ttl_days
        self.upload_url_factory = upload_url_factory or (
            lambda document_id, _key, _payload: f"r2-reservation://{document_id}"
        )
        self.object_metadata_reader = object_metadata_reader
        self._active_connection: ContextVar[Connection | None] = ContextVar(
            f"researchmate_postgres_uow_{id(self)}", default=None
        )

    @classmethod
    def from_database_url(
        cls,
        database_url: str,
        *,
        default_project_ttl_days: int = 7,
        upload_url_factory: UploadUrlFactory | None = None,
        object_metadata_reader: ObjectMetadataReader | None = None,
    ) -> PostgresRepositoryCore:
        """Build a repository backed by the supplied database URL."""
        engine = create_engine(
            _psycopg_url(database_url),
            pool_pre_ping=True,
            pool_recycle=300,
            future=True,
            # INFRA-4: Supabase free-tier Postgres caps connections well below the sum of
            # default pool_size (5) + max_overflow (10) across 4+ engines. Pinning to a
            # small total ceiling per engine keeps the platform from rejecting connections.
            pool_size=2,
            max_overflow=3,
        )
        return cls(
            engine,
            default_project_ttl_days=default_project_ttl_days,
            upload_url_factory=upload_url_factory,
            object_metadata_reader=object_metadata_reader,
        )

    @contextmanager
    def _transaction(self, user: CurrentUser | None = None) -> Iterator[Connection]:
        """Reuse the active unit of work or open one scoped transaction."""
        active = self._active_connection.get()
        if active is not None:
            yield active
            return
        with self.engine.begin() as connection:
            token = self._active_connection.set(connection)
            try:
                if user is not None:
                    connection.execute(
                        text("select set_config('request.jwt.claim.sub', :user_id, true)"),
                        {"user_id": str(user.id)},
                    )
                yield connection
            finally:
                self._active_connection.reset(token)
